/* The "Data Detective" form: What? Where? When? */
(function () {
  "use strict";
  const ETD = window.ETD;
  const $ = (id) => document.getElementById(id);

  const PRESETS = {
    desert: { type: "bbox", south: 23, west: 3, north: 27, east: 7, name: "Central Sahara" },
    rainforest: { type: "bbox", south: -5, west: -64, north: -1, east: -60, name: "Central Amazon" },
    arctic: { type: "bbox", south: 77, west: 13, north: 80, east: 18, name: "Svalbard (Arctic)" },
    city: { type: "bbox", south: 33.0, west: -112.6, north: 34.0, east: -111.5, name: "Phoenix, Arizona area" },
  };

  let variables = [];
  let region = null;

  const lastCompleteYear = () => new Date().getFullYear() - 1;

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function renderVariableCard() {
    const v = variables.find((x) => x.id === $("variable-select").value);
    if (!v) { $("variable-card").innerHTML = ""; return; }
    $("variable-card").innerHTML = `
      <p class="var-def">${escapeHtml(v.definition)}</p>
      <p><strong>Why it matters:</strong> ${escapeHtml(v.why_it_matters)}</p>
      <p class="muted small">Units: ${escapeHtml(v.units)} · Source: ${escapeHtml(v.source)}</p>
      <p class="muted small">💡 Try: <em>${escapeHtml(v.example_question)}</em></p>`;
  }

  function setVariables(list) {
    variables = list;
    const sel = $("variable-select");
    sel.innerHTML = "";
    const groups = {};
    list.forEach((v) => (groups[v.category] = groups[v.category] || []).push(v));
    Object.keys(groups).forEach((cat) => {
      const og = document.createElement("optgroup");
      og.label = cat;
      groups[cat].forEach((v) => {
        const o = document.createElement("option");
        o.value = v.id;
        o.textContent = `${v.name} (${v.units})`;
        og.appendChild(o);
      });
      sel.appendChild(og);
    });
    renderVariableCard();
  }

  function regionText(r) {
    if (!r) return "No region selected yet — click the map.";
    const nm = r.name ? `<strong>${escapeHtml(r.name)}</strong> · ` : "";
    if (r.type === "point") return `${nm}Point ${r.lat.toFixed(2)}°, ${r.lon.toFixed(2)}°`;
    return `${nm}Box ${r.south.toFixed(1)}° to ${r.north.toFixed(1)}° lat, ${r.west.toFixed(1)}° to ${r.east.toFixed(1)}° lon`;
  }

  function setRegion(r, clipped) {
    region = r;
    $("region-label").innerHTML =
      regionText(r) + (clipped ? ' <span class="warn">(shrunk to the 5° limit)</span>' : "");
  }

  function setYears(start, end) {
    $("start-year").value = start;
    $("end-year").value = end;
  }

  function setDeseasonalize(on) { $("deseasonalize").checked = !!on; }

  /** Validate the form and build an AnalyzeRequest body. Throws Error with a friendly message. */
  function buildRequest() {
    const variableId = $("variable-select").value;
    if (!variableId) throw new Error("Choose a variable first (step 1).");
    if (!region) throw new Error("Choose a region: click the map, draw a box, or search a place (step 2).");
    const start = parseInt($("start-year").value, 10);
    const end = parseInt($("end-year").value, 10);
    const last = lastCompleteYear();
    if (!Number.isInteger(start) || !Number.isInteger(end)) throw new Error("Enter both years (step 3).");
    if (start < ETD.config.FIRST_YEAR) throw new Error(`Data start in ${ETD.config.FIRST_YEAR}.`);
    if (end > last) throw new Error(`The last complete year of data is ${last}.`);
    if (end - start + 1 < ETD.config.MIN_YEARS) throw new Error(`Choose at least ${ETD.config.MIN_YEARS} years.`);
    return {
      variable_id: variableId,
      region,
      start_year: start,
      end_year: end,
      resolution: $("resolution").value,
      deseasonalize: $("deseasonalize").checked,
      alpha: parseFloat($("alpha").value),
    };
  }

  /** Fill the whole form from an AnalyzeRequest-like object (used by demos). */
  function fill(req) {
    $("variable-select").value = req.variable_id;
    renderVariableCard();
    setYears(req.start_year, req.end_year || lastCompleteYear());
    setDeseasonalize(req.deseasonalize !== false);
    $("resolution").value = req.resolution || "monthly";
    $("alpha").value = String(req.alpha || 0.05) === "0.1" ? "0.10" : String(req.alpha || 0.05);
    ETD.map.setRegion(req.region);
  }

  async function onSearch(e) {
    e.preventDefault();
    const q = $("place-input").value.trim();
    const list = $("search-results");
    list.innerHTML = "";
    list.hidden = true;
    if (q.length < 2) return;
    try {
      const results = await ETD.api.searchPlaces(q);
      results.slice(0, 6).forEach((r) => {
        const li = document.createElement("li");
        const b = document.createElement("button");
        b.type = "button";
        b.textContent = [r.name, r.region, r.country].filter(Boolean).join(", ");
        b.addEventListener("click", () => {
          list.hidden = true;
          ETD.map.setMode("point");
          ETD.map.setPoint(r.lat, r.lon, r.name);
        });
        li.appendChild(b);
        list.appendChild(li);
      });
      list.hidden = false;
    } catch (err) {
      ETD.app.showError(err.message);
    }
  }

  function init() {
    const last = lastCompleteYear();
    ["start-year", "end-year"].forEach((id) => { $(id).max = last; });
    setYears(ETD.config.FIRST_YEAR, last);
    $("variable-select").addEventListener("change", renderVariableCard);
    $("search-form").addEventListener("submit", onSearch);
    document.querySelectorAll(".chip[data-place]").forEach((chip) =>
      chip.addEventListener("click", () => ETD.map.setRegion(PRESETS[chip.dataset.place]))
    );
  }

  ETD.wizard = { init, setVariables, setRegion, buildRequest, fill, getRegion: () => region, lastCompleteYear, escapeHtml };
})();
