/* Where the FastAPI backend lives.
 *
 * - Live Server (VS Code, usually http://127.0.0.1:5500): API at http://127.0.0.1:8000
 * - Page served by FastAPI itself (port 8000) or by Netlify: same origin, relative "/api"
 *   (on Netlify, netlify.toml forwards /api/* to the Render backend).
 */
(function () {
  "use strict";
  const host = window.location.hostname;
  const isLocal = host === "localhost" || host === "127.0.0.1" || host === "";
  const servedByApi = window.location.port === "8000";
  window.ETD = window.ETD || {};
  window.ETD.config = {
    API_BASE: isLocal && !servedByApi ? "http://127.0.0.1:8000" : "",
    FIRST_YEAR: 1981,
    MIN_YEARS: 10,
    MAX_BOX_DEG: 5,
  };
})();
