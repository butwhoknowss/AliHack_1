/* Thin fetch wrappers for the backend /api endpoints. */
(function () {
  "use strict";
  const ETD = window.ETD;
  const base = () => ETD.config.API_BASE;

  class ApiError extends Error {
    constructor(message, status) {
      super(message);
      this.status = status;
    }
  }

  async function request(path, options = {}, timeoutMs = 180000) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    let resp;
    try {
      resp = await fetch(base() + path, { ...options, signal: ctrl.signal });
    } catch (err) {
      if (err.name === "AbortError") throw new ApiError("The request took too long. Please try again.", 0);
      throw new ApiError(
        "Backend not running. Double-click start-backend.bat in the project folder and keep its " +
          "window open — this page reconnects automatically.",
        0
      );
    } finally {
      clearTimeout(timer);
    }
    if (!resp.ok) {
      let msg = `Request failed (HTTP ${resp.status}).`;
      try {
        const body = await resp.json();
        if (body && body.detail) msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      } catch (_) { /* not JSON */ }
      throw new ApiError(msg, resp.status);
    }
    return resp;
  }

  const getJson = async (path) => (await request(path)).json();

  ETD.api = {
    ApiError,
    health: () => getJson("/api/health"),
    variables: () => getJson("/api/variables"),
    demos: () => getJson("/api/demos"),
    resources: () => getJson("/api/resources"),
    searchPlaces: (q) => getJson("/api/locations/search?q=" + encodeURIComponent(q)),
    currentWeather: (lat, lon) =>
      getJson(`/api/weather/current?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`),
    analyze: async (body) =>
      (await request("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })).json(),
    /** Download an export file (xlsx|csv) and save it via a temporary link. */
    exportAnalysis: async (analysisId, format) => {
      const resp = await request(`/api/export/${encodeURIComponent(analysisId)}?format=${format}`);
      const blob = await resp.blob();
      const cd = resp.headers.get("Content-Disposition") || "";
      const match = cd.match(/filename="([^"]+)"/);
      const name = match ? match[1] : `trend_export.${format}`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
  };
})();
