/* App state + wiring between the wizard, map, API, chart and result cards. */
(function () {
  "use strict";
  const ETD = window.ETD;
  const $ = (id) => document.getElementById(id);
  const fmt = (x) => ETD.charts.fmt(x);
  const fmtP = (p) => ETD.charts.fmtP(p);

  const state = { result: null, compare: null, busy: false };

  function showError(msg) {
    const el = $("form-error");
    el.textContent = msg;
    el.hidden = !msg;
    if (msg) el.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function setLoading(on, text) {
    state.busy = on;
    $("loading").hidden = !on;
    if (text) $("loading-text").textContent = text;
    $("investigate-btn").disabled = on;
  }

  function chartOpts() {
    return { showAnomaly: $("show-anomaly").checked, showCI: $("show-ci").checked };
  }

  function redraw() {
    if (state.result) ETD.charts.render(state.result, chartOpts(), state.compare);
  }

  /** Big number with its unit on a smaller line, so long units never break mid-word. */
  function setBig(id, number, unit) {
    const el = $(id);
    el.textContent = number;
    const span = document.createElement("span");
    span.className = "unit";
    span.textContent = unit;
    el.appendChild(span);
  }

  function renderCards(res) {
    const u = res.variable.units;
    const t = res.trend;
    const ols = t.ols;
    const mk = t.mann_kendall;

    setBig("card-rate", fmt(ols.slope_per_decade), `${u} per decade`);
    $("card-rate-ci").textContent = `95 % CI: ${fmt(ols.ci95_low_per_decade)} to ${fmt(ols.ci95_high_per_decade)} ${u}/decade`;
    setBig("card-total", fmt(t.total_change), u);
    $("card-total-sub").textContent =
      `over ${res.period[0]}–${res.period[1]}` + (t.percent_change !== null ? ` (${fmt(t.percent_change)} %)` : "");
    $("card-ols-p").textContent = fmtP(ols.p_value);
    $("card-ols-sub").textContent = `R² = ${ols.r_squared.toFixed(3)} · effective n ≈ ${Math.round(ols.n_effective)} of ${ols.n}`;
    $("card-mk-p").textContent = fmtP(mk.p_value);
    $("card-mk-sub").textContent = `${mk.trend} · Sen's slope ${fmt(mk.sens_slope_per_decade)} ${u}/decade (${mk.test.replace("_", "-")})`;

    const sig = $("card-sig");
    sig.classList.remove("sig-yes", "sig-mixed", "sig-no");
    const map = {
      both: ["YES ✔", "sig-yes", "Both tests agree"],
      ols_only: ["MIXED ≈", "sig-mixed", "Only the t-test agrees"],
      mk_only: ["MIXED ≈", "sig-mixed", "Only Mann-Kendall agrees"],
      neither: ["NOT YET ✖", "sig-no", "Could be natural variability"],
    };
    const [label, cls, sub] = map[t.agreement];
    sig.classList.add(cls);
    $("card-sig-value").textContent = label;
    $("card-sig-sub").textContent = `${sub} (α = ${res.alpha})`;

    $("verdict-text").textContent = t.verdict;
    const hints = $("hints");
    hints.innerHTML = "";
    t.hints.forEach((h) => {
      const li = document.createElement("li");
      li.textContent = h;
      hints.appendChild(li);
    });
    renderNextSteps(res);
    $("citation").textContent =
      `${res.n_sample_points} sample point(s) · ${Math.round(res.missing_fraction * 100)} % missing · ${res.source_citation}`;
  }

  function renderCompare(res, cmp) {
    const box = $("compare-verdict");
    if (!cmp) { box.hidden = true; box.innerHTML = ""; return; }
    const esc = ETD.wizard.escapeHtml;
    const dir = (r) => (r.trend.ols.slope_per_decade > 0 ? "▲ up" : r.trend.ols.slope_per_decade < 0 ? "▼ down" : "— flat");
    const same = Math.sign(res.trend.ols.slope_per_decade) === Math.sign(cmp.trend.ols.slope_per_decade);
    box.innerHTML = `
      <h3>Comparison</h3>
      <p><span class="swatch swatch-a"></span><strong>${esc(res.region.name || "Region A")}</strong>: ${dir(res)}
        ${fmt(res.trend.ols.slope_per_decade)} ${esc(res.variable.units)}/decade, ${fmtP(res.trend.ols.p_value)}
        (${res.trend.significant ? "significant" : "not significant"})</p>
      <p><span class="swatch swatch-b"></span><strong>${esc(cmp.region.name || "Region B")}</strong>: ${dir(cmp)}
        ${fmt(cmp.trend.ols.slope_per_decade)} ${esc(cmp.variable.units)}/decade, ${fmtP(cmp.trend.ols.p_value)}
        (${cmp.trend.significant ? "significant" : "not significant"})</p>
      <p class="muted">${same ? "Both regions trend in the same direction." : "The two regions trend in <strong>opposite directions</strong>."}</p>
      <p class="muted small">${esc(cmp.trend.verdict)}</p>`;
    box.hidden = false;
  }

  async function loadWeather(region) {
    const card = $("weather-card");
    const lat = region.type === "point" ? region.lat : (region.south + region.north) / 2;
    const lon = region.type === "point" ? region.lon : (region.west + region.east) / 2;
    try {
      const w = await ETD.api.currentWeather(lat, lon);
      const esc = ETD.wizard.escapeHtml;
      const icon = /^https:\/\//.test(w.icon) ? `<img src="${esc(w.icon)}" alt="" width="48" height="48" />` : "";
      $("weather-body").innerHTML = `
        <div class="weather-row">${icon}
          <div><strong>${esc(w.temp_c)} °C</strong> · ${esc(w.condition)}<br />
          <span class="muted small">${esc(w.location)}, ${esc(w.country)} · ${esc(w.local_time)}</span></div>
        </div>
        <p class="small">Feels like ${esc(w.feelslike_c)} °C · Humidity ${esc(w.humidity)} % · Wind ${esc(w.wind_kph)} km/h</p>`;
      card.hidden = false;
    } catch (_) {
      card.hidden = true; // optional feature: never block the analysis
    }
  }

  async function runAnalysis(req, compareReq) {
    if (state.busy) return;
    showError("");
    setLoading(true, compareReq ? "Fetching NASA data for two regions…" : "Fetching NASA data and testing for a trend…");
    const slowTimer = setTimeout(() => {
      $("loading-text").textContent = "Still working… the first request can take up to a minute (the server may be waking up or NASA POWER is busy).";
    }, 12000);
    try {
      const [res, cmp] = await Promise.all([
        ETD.api.analyze(req),
        compareReq ? ETD.api.analyze(compareReq) : Promise.resolve(null),
      ]);
      state.result = res;
      state.compare = cmp;
      $("show-anomaly").disabled = !res.deseasonalize;
      $("show-anomaly").checked = res.deseasonalize;
      $("chart-title").textContent =
        `${res.variable.name} — ${res.region.name || "selected region"} (${res.period[0]}–${res.period[1]})`;
      $("results").hidden = false;
      redraw();
      renderCards(res);
      renderCompare(res, cmp);
      loadWeather(res.region);
    } catch (err) {
      showError(err.message || String(err));
      if (err.status === 0 && /not running/.test(err.message)) {
        $("api-status").className = "api-status bad";
        startReconnecting();
      }
    } finally {
      clearTimeout(slowTimer);
      setLoading(false);
    }
  }

  async function onInvestigate() {
    let req;
    try {
      req = ETD.wizard.buildRequest();
    } catch (err) {
      showError(err.message);
      return;
    }
    if (ETD.demos.isActive()) ETD.demos.stop();
    ETD.map.setCompareBox(null);
    await runAnalysis(req, null);
  }

  async function exportAs(format) {
    if (!state.result) return;
    try {
      await ETD.api.exportAnalysis(state.result.analysis_id, format);
    } catch (err) {
      showError(err.message);
    }
  }

  async function checkHealth() {
    const el = $("api-status");
    try {
      const h = await ETD.api.health();
      el.textContent = h.nasa_power ? "● online" : "● online (NASA POWER unreachable)";
      el.className = "api-status " + (h.nasa_power ? "ok" : "warn");
      const gio = !h.giovanni_configured ? "no Earthdata login" : h.giovanni === null ? "checking…" : h.giovanni ? "ok" : `not working (${h.giovanni_error || "login rejected"})`;
      el.title = `NASA POWER: ${h.nasa_power ? "ok" : "down"} · NASA Giovanni: ${gio} · WeatherAPI: ${h.weatherapi ? "ok" : "off"} · storage: ${h.storage ? "ok" : "error"}`;
      return true;
    } catch (err) {
      el.textContent = "● backend offline";
      el.className = "api-status bad";
      el.title = err.message;
      return false;
    }
  }

  let catalogLoaded = false;
  let reconnectTimer = null;

  /** Resources panel, grouped by provider; every link opens in a new tab. */
  const STEP_LABELS = { data: "Get data", test: "Test", check: "Cross-check", explain: "Explain" };

  /** Resources grouped by detective step; each one lists the resources it connects to. */
  function renderResources(list, steps) {
    const esc = ETD.wizard.escapeHtml;
    const byKey = {};
    list.forEach((r) => { if (r.key) byKey[r.key] = r; });
    const order = (steps && steps.length) ? steps : [{ step: "", title: "Resources", intro: "" }];
    const groups = order.map((s) => ({ ...s, items: list.filter((r) => !s.step || r.step === s.step) }));
    const leftovers = steps && steps.length ? list.filter((r) => !steps.some((s) => s.step === r.step)) : [];
    if (leftovers.length) groups.push({ step: "", title: "More", intro: "", items: leftovers });

    const links = (r) => (r.related || []).filter((l) => byKey[l.key]).map((l) => `
        <li><a href="#res-${esc(l.key)}" class="res-jump" data-key="${esc(l.key)}">${esc(byKey[l.key].title)}</a>
          <span class="muted"> — ${esc(l.why)}</span></li>`).join("");

    $("resources-list").innerHTML = groups.filter((g) => g.items.length).map((g) => `
      <h3>${esc(g.title)}</h3>
      ${g.intro ? `<p class="muted small">${esc(g.intro)}</p>` : ""}
      <ul class="resource-items">${g.items.map((r) => `
        <li id="res-${esc(r.key)}">
          <a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">${esc(r.title)}</a>
          <span class="badge ${r.used_in_app ? "badge-used" : "badge-explore"}">${r.used_in_app ? "Used in this app" : "Explore further"}</span>
          <span class="badge badge-kind">${esc(r.provider)} · ${esc(r.kind)}</span>
          <p class="muted small">${esc(r.how_it_helps)}</p>
          ${links(r) ? `<p class="small connects">Connects to:</p><ul class="res-links small">${links(r)}</ul>` : ""}
        </li>`).join("")}
      </ul>`).join("");
  }

  /** Briefly highlight a resource when a "Connects to" link jumps to it. */
  function onResourceJump(ev) {
    const a = ev.target.closest(".res-jump");
    if (!a) return;
    ev.preventDefault();
    const el = document.getElementById("res-" + a.dataset.key);
    if (!el) return;
    $("resources-panel").open = true;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.classList.remove("res-flash");
    void el.offsetWidth; // restart the animation
    el.classList.add("res-flash");
  }

  function renderNextSteps(res) {
    const box = $("next-steps");
    const items = res.next_steps || [];
    if (!items.length) { box.hidden = true; return; }
    const esc = ETD.wizard.escapeHtml;
    $("next-steps-list").innerHTML = items.map((n) => `
      <li>
        <a href="${esc(n.url)}" target="_blank" rel="noopener noreferrer">${esc(n.title)}</a>
        ${STEP_LABELS[n.step] ? `<span class="badge badge-kind">${esc(STEP_LABELS[n.step])}</span>` : ""}
        <p class="muted small">${esc(n.why)}</p>
      </li>`).join("");
    box.hidden = false;
  }

  async function loadCatalog() {
    try {
      const [vars, demos] = await Promise.all([ETD.api.variables(), ETD.api.demos()]);
      ETD.wizard.setVariables(vars);
      ETD.demos.setDemos(demos);
      Promise.all([ETD.api.resources(), ETD.api.resourceSteps().catch(() => [])])
        .then(([list, steps]) => renderResources(list, steps)).catch(() => {
        $("resources-list").innerHTML = '<p class="muted">Resources could not be loaded.</p>';
      });
      catalogLoaded = true;
      showError("");
      return true;
    } catch (err) {
      showError(err.message);
      return false;
    }
  }

  /** While the backend is offline, retry every 5 s; load the catalog as soon as it is up. */
  function startReconnecting() {
    if (reconnectTimer) return;
    $("api-status").textContent = "● backend offline — retrying…";
    reconnectTimer = setInterval(async () => {
      try {
        await fetch(ETD.config.API_BASE + "/api/variables", { cache: "no-store" });
      } catch (_) {
        return; // still offline
      }
      clearInterval(reconnectTimer);
      reconnectTimer = null;
      if (!catalogLoaded) await loadCatalog();
      checkHealth();
    }, 5000);
  }

  async function init() {
    ETD.wizard.init();
    ETD.map.init((region, clipped) => ETD.wizard.setRegion(region, clipped));
    ETD.demos.init();

    $("investigate-btn").addEventListener("click", onInvestigate);
    $("show-anomaly").addEventListener("change", redraw);
    $("show-ci").addEventListener("change", redraw);
    // Re-colour the chart when the OS switches between light and dark mode.
    if (window.matchMedia) {
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      if (mq.addEventListener) mq.addEventListener("change", redraw);
    }
    $("export-xlsx").addEventListener("click", () => exportAs("xlsx"));
    $("export-csv").addEventListener("click", () => exportAs("csv"));
    $("resources-list").addEventListener("click", onResourceJump);

    const loaded = await loadCatalog();
    if (loaded) checkHealth();
    else startReconnecting();
  }

  ETD.app = { runAnalysis, showError };
  document.addEventListener("DOMContentLoaded", init);
})();
