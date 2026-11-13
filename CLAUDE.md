# CLAUDE.md

Guidance for Claude Code (and humans) working in this repository.

## Project

**Earth Trend Detective** is a 4-day hackathon tool built for the NASA Earth science trend challenge. Users pick a variable, a region and a period. The app shows the time series and tells them what is changing, where, by how much, and whether the trend is statistically significant. It uses an OLS t-test with a 95 % CI (autocorrelation-corrected) and Mann-Kendall with Sen's slope. The audience is high-school and college students and the science-curious public, so **all user-facing text must be plain language**.

**Read `Architecture.md` before structural changes.** It is the source of truth for endpoints, schemas, storage and statistics. Keep it in sync with the code.

## Stack

- **Backend:** FastAPI on uvicorn with **1 worker**, Python ≥ 3.12. Also httpx (async), pandas 3, statsmodels/scipy and pymannkendall.
- **Frontend:** static dashboard in `frontend/`: vanilla JS, with Leaflet and Plotly from pinned CDN URLs. **No build step.**
- **Storage:** **.xlsx files** in `data/` via openpyxl/pandas. **No database.**
- **Data:**
  - **NASA POWER**: long time series, no key needed.
  - **NASA Giovanni**: GPM, OMI, AIRS and GLDAS. Optional; needs a free Earthdata login.
  - **WeatherAPI.com**: search and current weather. The key is in `.env`.
- **Hosting:**
  - Local: **Live Server** (:5500) for the frontend, uvicorn (:8000) for the API.
  - Production: **Netlify** for the frontend, **Render** for the API.
  - **No Docker, no nginx.** Netlify's `/api/*` rewrite does the proxying.

## Commands

```bash
python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt
start-backend.bat                                           # Windows one-click: creates .venv if needed, runs uvicorn :8000
cd backend && uvicorn app.main:app --reload --port 8000     # same, manually (docs at /docs; also serves the dashboard at /)
# then in VS Code: right-click frontend/index.html -> Open with Live Server (http://127.0.0.1:5500)
pytest -q                                                   # from repo root; no network needed
ruff check .                                                # lint
```

## Layout

```
backend/app/
  main.py config.py errors.py deps.py
  models/    pydantic request/response schemas
  routers/   thin HTTP layer, all under /api
  sources/   nasa_power.py, giovanni.py, weatherapi.py (DataSource protocol in base.py)
  services/  region.py series.py trend.py explain.py analysis.py next_steps.py
  storage/   xlsx_store.py (ONLY place touching .xlsx), seed.py (default catalog + demos)
frontend/    index.html, css/styles.css, js/{config,api,map,charts,wizard,demos,app}.js
data/        catalog.xlsx (generated); cache.xlsx + analyses.xlsx (runtime, gitignored)
tests/       pytest + respx
netlify.toml render.yaml .vscode/settings.json
```

## Rules

1. **Secrets:** the WeatherAPI key and the Earthdata login live only in `.env` (gitignored) and in the Render dashboard. Never hardcode it, print it, or put it in docs or tests. Never log URLs that contain `key=`. `httpx` logging is silenced for this reason.
2. **Storage:** all `.xlsx` IO goes through `storage/xlsx_store.py`, using the file lock, a temp file and `os.replace`. Call it from async code via the `a*` wrappers.
3. **Single worker:** never run uvicorn with `--workers` above 1.
4. **Thin routers:** validation lives in pydantic models, logic in `services/`, upstream calls in `sources/`. Raise the errors in `errors.py`, not HTTPException, from services.
5. **Async HTTP:** use the shared `httpx.AsyncClient` on `app.state.http`. Never use `requests`.
6. **Statistics changes need tests:** add a synthetic-series test to `tests/test_trend.py`.
7. **Tests never hit the network:** mock with `respx`.
8. **Frontend:**
   - Use `ETD.config.API_BASE` + `/api/...` and never hardcode hosts.
   - Escape any server text inserted with innerHTML (`ETD.wizard.escapeHtml`).
   - Keep CDN versions pinned.
9. **User-facing text:** explain jargon (p-value, anomaly, significance) in plain words.

## Gotchas

- **NASA POWER:**
  - Monthly keys are `YYYYMM`; **month `13` is the annual mean**, so drop it.
  - The fill value is **−999**; convert it to NaN.
  - AG community units: radiation is **MJ/m²/day**, not kWh.
- **WeatherAPI.com history is too short for trends.** Use it only for `search.json` and `current.json`.
- **NASA Giovanni** (`sources/giovanni.py`):
  - **Point-only** API: boxes are capped at 3 × 3 points.
  - Monthly resolution only.
  - Each variable has its own `first_year`.
  - Values are converted with `value × scale + offset` from the catalog (e.g. AIRS kelvin −273.15, GPM mm/hr × 24).
- **Earthdata login for Giovanni:**
  - Use `EARTHDATA_USERNAME`/`PASSWORD`, which drives the `/signin` OAuth flow. An Earthdata user token alone was rejected in testing.
  - Basic auth must only ever be sent to `urs.earthdata.nasa.gov`.
  - Giovanni variables are disabled (`available=false`) until the startup `verify()` succeeds.
  - Tests must pass empty Earthdata settings so they never use the real `.env` login.
- **Giovanni data IDs** in `seed.py` were confirmed live (2026-11-13). `/gettoken` returns **JSON** `{expires_in, token}`, not a bare string. An unknown data ID returns **HTTP 403** "Data parameter is invalid" (not an auth error). MODIS MOD08 is not served by the API.
- **Sen's slope** from pymannkendall is per time step:
  - ×120 for Hamed-Rao on monthly anomalies
  - ×10 for `seasonal_test` (per year)
- **Limits:**
  - Analysis period: at least **10 years**, ending no later than the last complete year.
  - Box: at most **5° × 5°**, with ≤ 25 sample points for monthly data and ≤ 4 for daily.
  - Daily `/timeseries`: at most 10 years.
- **Live Server** reloads on any file change. `.vscode/settings.json` ignores `data/**`, `backend/**` and `*.xlsx`; keep it that way.
- **CSS:** `[hidden] { display: none !important; }` must stay. Flex components otherwise override the `hidden` attribute.
- **pandas 3:** copy-on-write is always on, so avoid chained assignment. Text columns use the `str` dtype.
- **Windows:** an `.xlsx` open in Excel is locked, so close it while the server runs.
- **Windows + `--reload`:** the real server is a child process (`multiprocessing spawn_main`). Killing only the parent leaves port 8000 held by an orphan, so kill the whole tree or use Ctrl+C.
- **Frontend reconnect:** if the backend is offline at page load, `app.js` polls every 5 s and loads the catalog once the backend is up.
- **Catalog changes:** after editing `seed.py` (variables, demos or `RESOURCES`), bump `SEED_VERSION`. `catalog.xlsx` is rebuilt at the next startup. The stored version also includes a hash of the sheet columns, so a column change in `xlsx_store.py` forces a rebuild too.
- **Resources:** each one needs a unique `key`, a `step` from `RESOURCE_STEPS` and `related` links to existing keys (a test checks this). `services/next_steps.py` refers to resources by `key`.
- **Netlify:** before deploying, replace `YOUR-RENDER-SERVICE` in `netlify.toml`.

## Git

- Don't commit `.env`, `data/cache.xlsx` or `data/analyses.xlsx`.
- Commit only when asked.
