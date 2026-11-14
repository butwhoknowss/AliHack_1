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

  const currentVariable = () => variables.find((x) => x.id === $("variable-select").value);

  // ---- display units (remembered per base unit, e.g. °F for every temperature variable) ----
  const UNIT_KEY = (base) => "etd-unit:" + base;

  function storedUnit(base) {
    try { return localStorage.getItem(UNIT_KEY(base)); } catch (_) { return null; }
  }

  function storeUnit(base, id) {
    try { localStorage.setItem(UNIT_KEY(base), id); } catch (_) { /* private mode: not remembered */ }
  }

  /** The viewer's remembered unit id for a variable, if that variable offers it. */
  function preferredUnit(variableId) {
    const v = variables.find((x) => x.id === variableId);
    if (!v || !v.unit_options) return undefined;
    const id = storedUnit(v.base_units || v.units);
    return id && id !== "base" && v.unit_options.some((o) => o.id === id) ? id : undefined;
  }

  function renderUnitSelect(v, wanted) {
    const opts = (v && v.unit_options) || [];
    const sel = $("unit-select");
    sel.innerHTML = "";
    opts.forEach((o) => {
      const el = document.createElement("option");
      el.value = o.id;
      el.textContent = o.label;
      sel.appendChild(el);
    });
    const pick = wanted || preferredUnit(v && v.id) || "base";
    sel.value = opts.some((o) => o.id === pick) ? pick : "base";
    $("unit-row").hidden = opts.length < 2;
  }

  function selectedUnitLabel(v) {
    const o = (v.unit_options || []).find((x) => x.id === $("unit-select").value);
    return o ? o.label : v.units;
  }

  function onUnitChange() {
    const v = currentVariable();
    if (!v) return;
    storeUnit(v.base_units || v.units, $("unit-select").value);
    renderVariableCard();
    if (ETD.app && ETD.app.checkDirty) ETD.app.checkDirty();
  }

  function renderVariableCard() {
    const v = currentVariable();
    if (!v) { $("variable-card").innerHTML = ""; return; }
    const satellite = v.provider === "giovanni"
      ? `<p class="badge-line"><span class="badge badge-sat">🛰️ Satellite data via NASA Giovanni</span></p>` : "";
    const warn = !v.available && v.unavailable_reason
      ? `<p class="warn small">⚠️ ${escapeHtml(v.unavailable_reason)}</p>` : "";
    $("variable-card").innerHTML = `
      ${satellite}
      <p class="var-def">${escapeHtml(v.definition)}</p>
      <p><strong>Why it matters:</strong> ${escapeHtml(v.why_it_matters)}</p>
      <p class="muted small">Units: ${escapeHtml(selectedUnitLabel(v))} · Data from ${escapeHtml(v.first_year)} · Source: ${escapeHtml(v.source)}</p>
      <p class="muted small">💡 Try: <em>${escapeHtml(v.example_question)}</em></p>
      ${warn}`;
  }

  /** Keep the year boxes inside the chosen variable's record. */
  function onVariableChange(wantedUnit) {
    const v = currentVariable();
    renderUnitSelect(v, typeof wantedUnit === "string" ? wantedUnit : undefined);
    renderVariableCard();
    if (!v) return;
    $("start-year").min = v.first_year;
    const start = parseInt($("start-year").value, 10);
    if (!Number.isInteger(start) || start < v.first_year) $("start-year").value = v.first_year;
    const daily = $("resolution").querySelector('option[value="daily"]');
    daily.disabled = v.provider === "giovanni";
    if (daily.disabled && $("resolution").value === "daily") $("resolution").value = "monthly";
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
        o.textContent = `${v.provider === "giovanni" ? "🛰️ " : ""}${v.name} (${v.units})` +
          (v.available ? "" : " — needs NASA Earthdata login");
        o.disabled = !v.available;
        og.appendChild(o);
      });
      sel.appendChild(og);
    });
    onVariableChange();
  }

  // ---- coordinates: hemisphere letters instead of minus signs (19.5°S, 75.4°W); same as Region.label() ----
  function fmtCoord(v, nd, pos, neg) {
    const r = Number(Number(v).toFixed(nd));
    if (r === 0) return `${(0).toFixed(nd)}°`;
    return `${Math.abs(r).toFixed(nd)}°${r > 0 ? pos : neg}`;
  }
  const fmtLat = (v, nd = 1) => fmtCoord(v, nd, "N", "S");
  const fmtLon = (v, nd = 1) =>
    Math.abs(Number(Number(v).toFixed(nd))) === 180 ? `${(180).toFixed(nd)}°` : fmtCoord(v, nd, "E", "W");

  /** Plain-text coordinates of a region: "64.80°N, 147.70°W" or "19.5°S–14.5°S, 75.4°W–70.4°W". */
  function coordText(r) {
    if (r.type === "point") return `${fmtLat(r.lat, 2)}, ${fmtLon(r.lon, 2)}`;
    return `${fmtLat(r.south)}–${fmtLat(r.north)}, ${fmtLon(r.west)}–${fmtLon(r.east)}`;
  }

  /** Name if the region has one, otherwise its coordinates (matches the backend's Region.label()). */
  function regionLabel(r) {
    if (!r) return "";
    if (r.name) return r.name;
    return r.type === "point" ? coordText(r) : `box ${coordText(r)}`;
  }

  function regionText(r) {
    if (!r) return "No region selected yet — click the map.";
    const nm = r.name ? `<strong>${escapeHtml(r.name)}</strong> · ` : "";
    return `${nm}${r.type === "point" ? "Point" : "Box"} ${escapeHtml(coordText(r))}`;
  }

  // ---- place names for clicked points / drawn boxes (reverse geocoding via the backend) ----
  const nameCache = new Map();          // "point:-17.00,-72.90" -> "El Chorro, Peru"
  let nameToken = 0;                    // ignore replies that arrive after a newer click
  let namePending = Promise.resolve();
  let regionClipped = false;

  function renderRegionLabel(looking) {
    $("region-label").innerHTML =
      regionText(region) +
      (regionClipped ? ' <span class="warn">(shrunk to the 5° limit)</span>' : "") +
      (looking ? ' <span class="muted small">· looking up the place name…</span>' : "");
  }

  function lookupName(r) {
    const token = ++nameToken;
    const lat = r.type === "point" ? r.lat : (r.south + r.north) / 2;
    const lon = r.type === "point" ? r.lon : (r.west + r.east) / 2;
    const key = `${r.type}:${lat.toFixed(2)},${lon.toFixed(2)}`;
    const lookup = nameCache.has(key)
      ? Promise.resolve(nameCache.get(key))
      : ETD.api.reverseGeocode(lat, lon, r.type).then((p) => { nameCache.set(key, p.label); return p.label; });
    namePending = lookup
      .then((label) => {
        if (token !== nameToken || region !== r || !label) return;
        region = { ...r, name: label };
        renderRegionLabel(false);
      })
      .catch(() => { if (token === nameToken) renderRegionLabel(false); }); // no name: coordinates stay
  }

  function setRegion(r, clipped) {
    region = r;
    regionClipped = !!clipped;
    const needsName = !!r && !r.name;
    renderRegionLabel(needsName);
    if (needsName) lookupName(r);
    else { nameToken++; namePending = Promise.resolve(); }
    if (ETD.app && ETD.app.checkDirty) ETD.app.checkDirty();
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
    const v = currentVariable();
    if (v && !v.available) throw new Error(v.unavailable_reason || "This variable is not available right now.");
    if (!region) throw new Error("Choose a region: click the map, draw a box, or search a place (step 2).");
    const start = parseInt($("start-year").value, 10);
    const end = parseInt($("end-year").value, 10);
    const last = lastCompleteYear();
    if (!Number.isInteger(start) || !Number.isInteger(end)) throw new Error("Enter both years (step 3).");
    const firstYear = v ? v.first_year : ETD.config.FIRST_YEAR;
    if (start < firstYear) throw new Error(`Data for this variable start in ${firstYear}.`);
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
      ...($("unit-select").value && $("unit-select").value !== "base" ? { units: $("unit-select").value } : {}),
    };
  }

  /** Fill the whole form from an AnalyzeRequest-like object (used by demos). */
  function fill(req) {
    $("variable-select").value = req.variable_id;
    setYears(req.start_year, req.end_year || lastCompleteYear());
    onVariableChange(req.units || undefined);
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
    $("variable-select").addEventListener("change", () => onVariableChange());
    $("unit-select").addEventListener("change", onUnitChange);
    $("search-form").addEventListener("submit", onSearch);
    document.querySelectorAll(".chip[data-place]").forEach((chip) =>
      chip.addEventListener("click", () => ETD.map.setRegion(PRESETS[chip.dataset.place]))
    );
  }

  ETD.wizard = { init, setVariables, setRegion, buildRequest, fill, getRegion: () => region, lastCompleteYear, escapeHtml, preferredUnit, regionLabel, whenNamed: () => namePending };
})();
