/* Leaflet map: click for a point, draw a rectangle for a box (max 5° per side). */
(function () {
  "use strict";
  const ETD = window.ETD;

  let map, marker, rect, drawer, compareRect;
  let mode = "point";
  let onChange = () => {};

  const round = (x, d = 3) => Math.round(x * 10 ** d) / 10 ** d;
  const clamp = (x, lo, hi) => Math.min(hi, Math.max(lo, x));

  function boxStyle(color) {
    return { color, weight: 2, fillOpacity: 0.12 };
  }

  /** Keep a box inside the world and no larger than MAX_BOX_DEG per side (shrinks around its centre). */
  function normaliseBox(south, west, north, east) {
    const max = ETD.config.MAX_BOX_DEG;
    let clipped = false;
    const cLat = (south + north) / 2;
    const cLon = (west + east) / 2;
    if (north - south > max) { south = cLat - max / 2; north = cLat + max / 2; clipped = true; }
    if (east - west > max) { west = cLon - max / 2; east = cLon + max / 2; clipped = true; }
    south = clamp(south, -90, 90); north = clamp(north, -90, 90);
    west = clamp(west, -180, 180); east = clamp(east, -180, 180);
    return { south: round(south), west: round(west), north: round(north), east: round(east), clipped };
  }

  function clearShapes() {
    if (marker) { map.removeLayer(marker); marker = null; }
    if (rect) { map.removeLayer(rect); rect = null; }
  }

  function enableDrawing() {
    if (drawer) drawer.disable();
    if (mode !== "bbox") return;
    drawer = new L.Draw.Rectangle(map, { shapeOptions: boxStyle("#d55e00"), showArea: false });
    drawer.enable();
  }

  function setPoint(lat, lon, name, fly = true) {
    clearShapes();
    lat = round(clamp(lat, -90, 90));
    lon = round(clamp(lon, -180, 180));
    marker = L.marker([lat, lon]).addTo(map);
    if (fly) map.setView([lat, lon], Math.max(map.getZoom(), 5));
    onChange({ type: "point", lat, lon, name: name || null });
  }

  function setBox(south, west, north, east, name, fly = true) {
    clearShapes();
    const b = normaliseBox(south, west, north, east);
    rect = L.rectangle([[b.south, b.west], [b.north, b.east]], boxStyle("#d55e00")).addTo(map);
    if (fly) map.fitBounds(rect.getBounds(), { padding: [30, 30], maxZoom: 7 });
    onChange({ type: "bbox", south: b.south, west: b.west, north: b.north, east: b.east, name: name || null }, b.clipped);
    enableDrawing();
  }

  /** Show (or clear) a second region used by comparison demos. */
  function setCompareBox(region) {
    if (compareRect) { map.removeLayer(compareRect); compareRect = null; }
    if (!region) return;
    compareRect = L.rectangle([[region.south, region.west], [region.north, region.east]], boxStyle("#0072b2")).addTo(map);
    const group = L.featureGroup([compareRect].concat(rect ? [rect] : []));
    map.fitBounds(group.getBounds(), { padding: [30, 30] });
  }

  function setRegion(region, fly = true) {
    if (!region) return;
    if (region.type === "point") {
      setMode("point");
      setPoint(region.lat, region.lon, region.name, fly);
    } else {
      setMode("bbox");
      setBox(region.south, region.west, region.north, region.east, region.name, fly);
    }
  }

  function setMode(newMode) {
    mode = newMode;
    const radio = document.querySelector(`input[name="region-mode"][value="${newMode}"]`);
    if (radio) radio.checked = true;
    enableDrawing();
  }

  function init(callback) {
    onChange = callback;
    map = L.map("map", { worldCopyJump: true, minZoom: 2 }).setView([20, 0], 2);
    // OSM's current tile policy: use the single host (the a./b./c. subdomains are deprecated).
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 12,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(map);

    map.on("click", (e) => {
      if (mode !== "point") return;
      const ll = e.latlng.wrap();
      setPoint(ll.lat, ll.lng, null, false);
    });

    map.on(L.Draw.Event.CREATED, (e) => {
      const b = e.layer.getBounds();
      const sw = b.getSouthWest().wrap();
      const ne = b.getNorthEast().wrap();
      if (sw.lng > ne.lng) {
        ETD.app && ETD.app.showError("Boxes crossing the date line (180°) are not supported. Draw it on one side.");
        enableDrawing();
        return;
      }
      setBox(sw.lat, sw.lng, ne.lat, ne.lng, null, false);
    });

    document.querySelectorAll('input[name="region-mode"]').forEach((r) =>
      r.addEventListener("change", () => setMode(r.value))
    );

    // Leaflet needs a size refresh when the layout changes.
    window.addEventListener("resize", () => map.invalidateSize());
  }

  ETD.map = { init, setRegion, setPoint, setBox, setCompareBox, setMode, getMode: () => mode };
})();
