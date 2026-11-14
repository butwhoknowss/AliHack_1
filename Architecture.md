# Architecture: Earth Trend Detective

This document is the source of truth for how the system is built. `README.md` is for users and `CLAUDE.md` is for contributors and AI assistants. If the code and this document disagree, fix one of them in the same change.

---

## 1. Goals and non-goals

**Goals (mapped to the challenge objectives)**

1. **Select** an Earth science variable from a curated catalog with plain-English definitions.
2. **Acquire** that variable for a user-chosen **region** (point or box) and period.
3. **Visualize** the time series: raw or deseasonalized values, a 12-month running mean, the trend line and a 95 % band.
4. **Analyze** the rate of change, the total change, and significance, using an **OLS t-test with a 95 % CI** (autocorrelation-corrected) and **Mann-Kendall with Sen's slope**.
5. **Teach** through the guided What/Where/When form, narrated demos and plain-language verdicts.

**Non-goals (4-day scope)**

- Non-linear trends, change-point detection, gridded trend maps.
- User accounts and authentication.
- Running more than one backend process. The `.xlsx` store assumes a single writer (§7).

---

## 2. System overview

```
 LOCAL DEVELOPMENT
 ┌────────────────────────────┐    fetch http://127.0.0.1:8000/api/*   ┌──────────────────────────┐
 │ Browser                    │ ─────────────────────────────────────▶ │ FastAPI (uvicorn :8000)  │
 │ VS Code Live Server :5500  │        (CORS allows :5500)             │  backend/app             │
 │ serves frontend/           │                                        └──────┬──────────┬────────┘
 └────────────────────────────┘                                               │ httpx    │ openpyxl
                                                                              ▼          ▼
 PRODUCTION                                                       NASA POWER API   data/*.xlsx
 ┌─────────────────────┐  /api/* (proxy rewrite, 200) ┌──────────────────────┐ WeatherAPI.com
 │ Netlify (static)    │ ───────────────────────────▶ │ Render web service   │
 │ publish = frontend/ │                              │ FastAPI (uvicorn)    │
 └─────────────────────┘                              └──────────────────────┘
```

| Layer | Technology | Responsibility |
|---|---|---|
| Static hosting | **Live Server** locally, **Netlify** in production | Serve `frontend/`. Netlify also proxies `/api/*` to Render, the job nginx would normally do. |
| API | **FastAPI** on **uvicorn**, 1 worker (Python ≥ 3.12) | Validation, orchestration, statistics, export |
| Long time series | **NASA POWER** REST API (no key) | Monthly/daily point data from 1981. Meteorology from MERRA-2; radiation from CERES/FLASHFlux. |
| Satellite / land-model series | **NASA Giovanni** time-series API (free Earthdata login) | GPM, OMI, AIRS and GLDAS monthly point data from 2000–2005. Optional: disabled without a working login. |
| Geocoding + "right now" | **WeatherAPI.com** (key in `.env`) | Place search → lat/lon, plus the current-conditions card |
| Storage | **.xlsx** via `openpyxl` + `pandas` | Variable catalog, demos, monthly response cache, saved analyses |
| Frontend | Vanilla JS with **Leaflet 1.9.4**, **Leaflet.draw 1.0.4** and **Plotly 2.35.2**, all from pinned CDNs | Dashboard UI. No build step. |

**Why not Docker or nginx?** The team deploys from GitHub to Netlify, which only serves static files and can't run Python. The backend therefore runs on Render. Netlify's `/api/*` rewrite in `netlify.toml` replaces nginx's reverse proxy, so in production the browser only talks to the Netlify domain.

**Why WeatherAPI.com is not the trend source:** its history only reaches back a few days on the free plan, and a trend test needs at least 10 years of monthly data. It is used for search and current conditions only. Every time-series provider sits behind the `DataSource` protocol (§6). NASA POWER and NASA Giovanni are implemented; each catalog variable names its `provider`.

---

## 3. Repository layout

```
Hackathon_1/
├── README.md  CLAUDE.md  Architecture.md
├── requirements.txt           # pinned; Python >= 3.12
├── pyproject.toml             # pytest + ruff config
├── .env.example               # template; real .env is gitignored
├── netlify.toml               # publish=frontend, /api/* -> Render
├── render.yaml                # Render Blueprint for the API
├── .vscode/settings.json      # Live Server root=frontend, ignore data/backend changes
├── backend/app/
│   ├── main.py                # create_app(): lifespan, CORS, error handlers, routers, static mount
│   ├── config.py              # Settings (pydantic-settings, reads repo-root .env)
│   ├── errors.py              # UpstreamError 502, UpstreamTimeout 504, NotFoundError 404, DataQualityError 422
│   ├── deps.py                # accessors for objects on app.state
│   ├── models/requests.py     # Region, AnalyzeRequest (+ validators)
│   ├── models/responses.py    # Variable, SeriesPoint, OLSResult, MannKendallResult, TrendResult, AnalyzeResponse, ...
│   ├── routers/               # health, variables, resources, locations, weather, timeseries, analyze, demos, export
│   ├── sources/               # base.py (DataSource), nasa_power.py, giovanni.py, weatherapi.py
│   ├── services/              # region.py, series.py, trend.py, explain.py, analysis.py, next_steps.py
│   └── storage/               # xlsx_store.py (ONLY .xlsx IO), seed.py (default catalog)
├── frontend/
│   ├── index.html
│   ├── css/styles.css
│   └── js/ config.js api.js map.js charts.js wizard.js demos.js app.js
├── data/                      # catalog.xlsx (generated, committed); cache.xlsx, analyses.xlsx (runtime, gitignored)
└── tests/                     # conftest.py, test_trend.py, test_nasa_power.py, test_giovanni.py, test_xlsx_store.py, test_api.py
```

---

## 4. Configuration (`app/config.py`)

`pydantic-settings` reads environment variables and the **repo-root** `.env`, so it works no matter which folder uvicorn is started from.

| Variable | Default | Notes |
|---|---|---|
| `WEATHERAPI_KEY` | `""` | If empty, search and current weather return 502 and the dashboard hides that card. Trends still work. Never log it. |
| `NASA_POWER_BASE_URL` | `https://power.larc.nasa.gov/api` | |
| `WEATHERAPI_BASE_URL` | `https://api.weatherapi.com/v1` | |
| `DATA_DIR` | `./data` | Resolved against the repo root when relative |
| `CACHE_TTL_DAYS` | `30` | Older cached series are fetched again |
| `HTTP_TIMEOUT_SECONDS` | `60` | NASA POWER can be slow |
| `LOG_LEVEL` | `INFO` | `httpx`/`httpcore` are forced to WARNING because their INFO lines include full URLs, which would contain the key |
| `GIOVANNI_BASE_URL` | `https://api.giovanni.earthdata.nasa.gov` | |
| `EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD` | `""` | NASA Earthdata login used for Giovanni's `/signin` OAuth flow. This is the recommended option. Never logged. |
| `EARTHDATA_TOKEN` | `""` | Fallback: an Earthdata user token sent as a Bearer header. Giovanni rejected one in testing (2026-11), so prefer username and password. |
| `CORS_ORIGINS` | `""` | Extra comma-separated origins. `http://127.0.0.1:5500`/`5501` and `http://localhost:5500`/`5501` are always allowed. |

---

## 5. API specification

Base path: `/api`. Errors always look like `{"detail": "<human-readable message>"}`. Validation errors are flattened into one readable string.

### 5.1 Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | `{status, nasa_power, weatherapi, storage, weatherapi_configured, giovanni_configured, giovanni, giovanni_error}`. Upstream checks are cached for 5 minutes. |
| GET | `/api/variables?category=&q=` | Catalog list, with optional filters. Each variable includes `provider` (`power`/`giovanni`), `first_year`, `available`, `unavailable_reason`, `base_units` and `unit_options: [{id, label}]` (§5.5). |
| GET | `/api/resources` | Official challenge resources: `{key, step, topics, title, provider, kind, url, how_it_helps, used_in_app, related: [{key, why}]}` |
| GET | `/api/resources/steps` | The detective workflow the resources are grouped by: `[{step, title, intro}]` (data → test → check → explain) |
| GET | `/api/variables/{id}` | One variable (404 if unknown) |
| GET | `/api/locations/search?q=` | Place name → `[{name, region, country, lat, lon}]` (404 if nothing matches) |
| GET | `/api/locations/reverse?lat=&lon=&kind=point\|bbox` | Nearest named place (WeatherAPI search with `q=lat,lon`) plus `distance_km` and a `label` that is honest about distance (`services/places.py`): point ≤ 50 km "El Chorro, Peru", ≤ 150 km "near …", farther "≈470 km from …"; box ≤ 150 km "area around …". 404 if nothing found. |
| GET | `/api/weather/current?lat=&lon=` | Current conditions |
| GET | `/api/timeseries?variable_id=&start_year=&end_year=&resolution=&lat=&lon=` or `&south=&west=&north=&east=`, optional `&units=` | Raw regional series without statistics. Daily requests are limited to 10 years. |
| POST | `/api/analyze` | **Main endpoint**: time series plus full trend analysis. The result is saved unless `save:false`. |
| GET | `/api/analyses/{analysis_id}` | Re-creates a saved analysis from its stored request. The series comes from the cache. The id is 32 hex characters. |
| GET | `/api/demos` | Demo scenarios: `{demo_id, title, story, request, compare_request?, narration_steps[]}`. `end_year: null` means the frontend fills in the last complete year. |
| GET | `/api/export/{analysis_id}?format=xlsx\|csv` | xlsx has two sheets, `summary` and `series`. The csv holds the series only and is UTF-8 with a BOM so Excel shows °C correctly. |

### 5.2 Request schema

```python
class Region(BaseModel):
    type: Literal["point", "bbox"]
    lat, lon: float | None                    # point; ranges ±90 / ±180
    south, west, north, east: float | None    # bbox
    name: str | None                          # display label (max 120 chars)
    # label(): the name, else hemisphere coordinates without minus signs:
    #   point "64.80°N, 147.70°W"; box "box 19.5°S–14.5°S, 75.4°W–70.4°W"
    #   (fmt_lat / fmt_lon / fmt_range; frontend twin: ETD.wizard.regionLabel)
    # validator: point needs lat+lon; bbox needs all 4, south<north, west<east
    #            (no dateline crossing), each side <= 5 degrees

class AnalyzeRequest(BaseModel):
    variable_id: str
    region: Region
    start_year: int        # >= 1981
    end_year: int          # <= last complete year (today.year - 1)
    resolution: Literal["monthly", "daily"] = "monthly"
    deseasonalize: bool = True
    alpha: float = 0.05    # 0 < alpha < 0.5
    save: bool = True
    units: str | None = None   # id from Variable.unit_options (e.g. "degF"); None = the variable's own unit
    # validator: end_year - start_year + 1 >= 10
```

### 5.3 Response schema (`AnalyzeResponse`)

| Field | Meaning |
|---|---|
| `analysis_id` | uuid4 hex |
| `variable`, `region`, `resolution`, `deseasonalize`, `alpha`, `period` | Echo of the request. `variable.units` is the unit the results are in (the chosen one); `variable.base_units` is the catalog unit. |
| `series[]` | `{date, value, anomaly}`, monthly. `anomaly` is null if not deseasonalized. |
| `trend_line[]` | OLS fitted values, on the anomaly scale when deseasonalized |
| `ci_band[]` | `{date, low, high}`: 95 % confidence band of the fitted mean |
| `trend.ols` | `slope_per_year`, `slope_per_decade`, `intercept` (trend-line value at the first month), `ci95_low/high_per_decade`, `t_stat`, `p_value`, `r_squared`, `n`, `n_effective` |
| `trend.mann_kendall` | `test` (`hamed_rao`, `seasonal` or `original`), `trend`, `p_value`, `z`, `tau`, `s`, `sens_slope_per_decade` |
| `trend.total_change` | OLS slope per year × number of years |
| `trend.percent_change` | Relative to the period mean. Null for temperatures (°C is not a ratio scale). |
| `trend.significant` / `agreement` | `significant` is true only when both tests have p < α. `agreement` is one of `both`, `ols_only`, `mk_only`, `neither`. |
| `trend.verdict`, `trend.hints[]` | Plain-language text |
| `missing_fraction`, `n_sample_points`, `source_citation`, `created_at` | |
| `next_steps` | Up to 4 `{key, title, url, step, why}`: challenge resources chosen for this variable, place and result (`services/next_steps.py`). Added by `POST /api/analyze` and `GET /api/analyses/{id}`. |

### 5.5 Display units (`services/units.py`)

Users can show results in another unit. Every option is linear (`value × factor + offset`). The conversion is applied to the monthly series **before** the statistics, so:
- **Slopes, confidence intervals, total change and the series:** scale with the unit.
- **p-values, `significant` and `agreement`:** unchanged.
- **Anomalies:** unaffected by the offset.

`variable.units` is replaced by the chosen label, so the verdict, cards, chart and export all use it with no other code involved. The cache keeps base-unit values.

| Base unit | Options (id → label) |
|---|---|
| °C | `degF` → °F (×1.8 + 32), `K` → K (+273.15) |
| mm/day | `mm_month` → mm/month (× 365.25/12, an average month), `mm_year` → mm/year (×365.25), `in_year` → inches/year (×365.25/25.4) |
| m/s | `km_h` → km/h, `mph` → mph, `knots` → knots |
| kPa | `hPa` → hPa (×10), `inHg` → inHg (÷3.386389) |
| MJ/m²/day | `kWh_m2_day` → kWh/m²/day (÷3.6), `W_m2` → W/m² (×10⁶/86400) |
| fraction (0–1) | `percent` → % (0–100) (×100) |

- `%`, `g/kg`, `DU` and `AOD` have no alternatives.
- Options are keyed by the catalog unit string, so a new variable with one of these units gets them automatically.
- `base` (or omitting `units`) means no conversion; an id not offered for the variable returns 422.
- Temperatures stay non-ratio, so there is no percent change in °F or K either.
- **Frontend:** a "Show results in" picker under the variable, hidden when there is only one unit. The choice is remembered per base unit in `localStorage` (`etd-unit:<base unit>`), so °F applies to every temperature variable and to the demos.

### 5.4 Status codes

| Code | When |
|---|---|
| 200 | Success |
| 404 | Unknown variable, analysis id, or place |
| 422 | Validation errors; too many missing months (> 20 %, e.g. soil moisture over the ocean); `start_year` before the variable's `first_year`; daily resolution for a Giovanni variable; a Giovanni variable without a working Earthdata login |
| 502 | NASA POWER or WeatherAPI returned an error, a bad payload, or an invalid key |
| 504 | Upstream timeout after retries |

---

## 6. Data sources

### 6.1 `DataSource` protocol (`sources/base.py`)

```python
async def fetch_point(variable_id, lat, lon, start_year, end_year, resolution) -> pd.Series
# float Series indexed by Timestamp (month start or day); NaN = missing
```

### 6.2 NASA POWER (`sources/nasa_power.py`)

- Monthly: `GET {base}/temporal/monthly/point?parameters=ID&community=AG&latitude=..&longitude=..&start=YYYY&end=YYYY&format=JSON`
- Daily: the same request on `/temporal/daily/point` with `start=YYYYMMDD&end=YYYYMMDD`
- Parsing (`parse_power_payload`) reads `properties.parameter[ID]` and handles these gotchas:
  - Monthly keys are `YYYYMM`, and **month `13` is the annual mean, so it is dropped**.
  - `header.fill_value` (−999) and any value ≤ −998 become NaN.
- Requests go through one shared `httpx.AsyncClient` with `asyncio.Semaphore(4)`. They retry twice with exponential backoff on 429/5xx/timeouts; other 4xx errors are not retried.
- `ping()` requests one year of T2M at (0, 0).
- **Units are those of the AG community** (verified live): T2M* °C, PRECTOTCORR mm/day, RH2M %, QV2M g/kg, GWET* fraction, WS2M m/s, ALLSKY_SFC_SW_DWN **MJ/m²/day**, PS kPa.

### 6.3 Variable catalog (`storage/seed.py` → `data/catalog.xlsx`)

There are 17 variables:
- **NASA POWER (11):** T2M, T2M_MAX, T2M_MIN, PRECTOTCORR, RH2M, QV2M, GWETTOP, GWETROOT, WS2M, ALLSKY_SFC_SW_DWN and PS.
- **NASA Giovanni (6):** see §6.5.

Each has `name`, `category`, `units`, `definition`, `why_it_matters`, `example_question`, `source` and `seasonal`. Each also has `provider`, `provider_id` (the upstream data ID), `first_year`, `scale` and `offset`. Upstream values are converted to display units with `value × scale + offset`.

The catalog also holds `RESOURCES` (13 official challenge resources) and a `meta` sheet with `seed_version`.

There are 3 demos:
- `alaska-warming` (T2M)
- `sahel-rainfall` (PRECTOTCORR)
- `opposite-trends` (PRECTOTCORR, Sahel vs. Arizona, with a `compare_request`)

At startup the catalog is created, or **rebuilt automatically when its stored `seed_version` differs from `SEED_VERSION` in `seed.py`**. To change the catalog, edit `seed.py`, bump `SEED_VERSION` and restart.

### 6.4 WeatherAPI.com (`sources/weatherapi.py`)

- `search.json?key=&q=` and `current.json?key=&q=lat,lon`. Protocol-relative icon URLs are made `https:`.
- Error mapping:
  - 401/403 → "key invalid" (502)
  - 400 with error code 1006 → 404 (no location)
  - other errors → 502
- The key is a query parameter, so request URLs are never logged (see §4).

### 6.5 NASA Giovanni (`sources/giovanni.py`)

- **Request:** `GET {base}/timeseries?data=<provider_id>&location=[lat,lon]&time=YYYY-01-01T00:00:00/YYYY-12-31T23:59:59`.
  - **Points only:** the API returns no area averages, so a box is sampled at up to 3 × 3 = 9 points and averaged.
  - Concurrency is limited to 2 with retries on 429/5xx. The timeout is 120 s.
- **Auth:**
  - With `EARTHDATA_USERNAME`/`PASSWORD` set: the app runs Giovanni's `/signin` flow. The redirect goes to `urs.earthdata.nasa.gov/oauth/authorize` with HTTP Basic auth, sent only to that host. That redirects to `/gettoken`, which answers JSON `{"expires_in": 86400, "token": "…"}` (`parse_signin_token`; a bare quoted string is also accepted). The token is cached until 5 minutes before `expires_in`, sent as the `authorizationtoken` header, and refreshed once on 401/403. Confirmed live on 2026-11-13.
  - With only `EARTHDATA_TOKEN` set: the token is sent as `Authorization: Bearer` and `authorizationtoken`.
  - Live test on 2026-11-13: a valid Earthdata user token (not expired) was rejected ("Failed validating user token" / HTTP 500), so username and password is the documented path.
  - The user must also have approved the Giovanni app in Earthdata Login once, by logging in at giovanni.gsfc.nasa.gov.
- **Startup check:** `verify()` runs once in the background (one year, one point, first Giovanni variable). Until it succeeds, Giovanni variables report `available=false` with a plain-language `unavailable_reason`, and `/api/analyze` returns 422. The specific failure (wrong password, approval page, sign-in HTTP status, Giovanni's answer) is kept in `last_error`, shown in `unavailable_reason` and in `/api/health` as `giovanni_error`.
- **Error quirk:** Giovanni answers **HTTP 403** with body `"Data parameter is invalid"` for an unknown data ID. This is reported as an unknown ID, not as a login failure. A recognised but disabled dataset answers 404 "currently unavailable".
- **Parsing** (`parse_giovanni_csv`): skip the metadata lines up to the row starting with `Timestamp`, then read `time,value` rows. `fill_value`/`undef` from the metadata and common fill values (−9999, 1e15, …) become NaN. Any time step is averaged to calendar months (`to_month_start`). Then `scale`/`offset` are applied.
- **Variables:**

  | id | provider_id | Conversion | From |
  |---|---|---|---|
  | GPM_PRECIP | `GPM_3IMERGM_07_precipitation` | mm/hr × 24 → mm/day | 2001 |
  | OMI_AOD | `OMAERUVd_003_FinalAerosolOpticalDepth500` (daily → monthly) | none (AOD) | 2005 |
  | OMI_OZONE | `OMTO3d_003_ColumnAmountO3` (daily → monthly) | none (DU) | 2005 |
  | AIRS_TSURF | `AIRS3STM_7_0_SurfAirTemp_A` | K − 273.15 → °C | 2003 |
  | GLDAS_EVAP | `GLDAS_NOAH025_M_2_1_Evap_tavg` | kg/m²/s × 86400 → mm/day | 2000 |
  | GLDAS_RUNOFF | `GLDAS_NOAH025_M_2_1_Qs_acc` | kg/m² per 3 h × 8 → mm/day | 2000 |

  All six IDs were confirmed live on 2026-11-13 (Kansas and Amazon points, 2019–2020; values in the expected ranges after conversion). MODIS `MOD08_M3` aerosol IDs are **not** served by the Giovanni API ("Data parameter is invalid"), so aerosols come from OMI. MERRA-2 IDs are recognised but "currently unavailable".

### 6.6 Official resources (`RESOURCES` → `GET /api/resources`)

There are 13 entries from the challenge's Resources tab. Each URL was checked to return HTTP 200 when it was added.

**How the resources relate.** They are not a flat list. Each one fits one step of a trend investigation (`RESOURCE_STEPS`), and the steps are what the dashboard panel groups by:

| Step | Resources | Role |
|---|---|---|
| 1 · data | Giovanni, Hydrology Time Series, AppEEARS | Turn satellite or model data for a place into a time series |
| 2 · test | trend-tests article, significance guide, SeaWiFS paper | How to decide whether a trend is real (the paper is a worked NASA example of the same recipe) |
| 3 · check | NOAA CDO, KNMI Climate Explorer | Independent cross-checks: station records and other datasets |
| 4 · explain | RCM, SWOT, Geo.ca, ecosystems page, SAR tutorial | Why a change matters, plus Canadian data and missions |

The key cross-links are stored per resource as `related: [[key, why], ...]` (shown as "Connects to:" in the panel):
- **Giovanni ↔ Hydrology Time Series:** Giovanni replaced the retired tool for GLDAS data.
- **Giovanni ↔ SeaWiFS paper:** the paper built its series in Giovanni.
- **Giovanni ↔ AppEEARS:** coarse long series vs. fine land detail; AppEEARS serves MODIS, which Giovanni's API doesn't.
- **CDO ↔ KNMI:** two independent cross-checks.
- **Trend tests ↔ significance guide ↔ SeaWiFS paper:** theory, basics, worked example.
- **RCM ↔ SAR tutorial / ecosystems page / Geo.ca:** the radar mission, how to use its images, what it monitors, and Canadian context.
- **SWOT ↔ Hydrology / significance guide:** measured vs. modelled water, and why a record from 2022 is too short for a trend.

`tests/test_next_steps.py` checks that every link points to an existing resource.

**Next steps after an analysis** (`services/next_steps.py`). The same relationships drive up to 4 suggestions per result, each with a reason written for that case:
- Station-measurable variables (temperature, rain, humidity, wind, pressure) → CDO first.
- The verdict picks the statistics resource:
  - "neither" → significance guide ("not significant ≠ no change")
  - mixed → trend-tests article (why the tests differ)
  - both → trend-tests article
- Giovanni variables → Giovanni (map the whole region).
- Soil moisture and evaporation → AppEEARS.
- Runoff → SWOT; other Giovanni water variables → Hydrology Time Series.
- A region in or near Canada (rough box test, no borders file) → Geo.ca and RCM.
- Then KNMI, then the SeaWiFS paper when seasons were removed.

Two original links were replaced with verified equivalents:
- The Hydrology Data Rods service redirects to a GES DISC notice that it has been discontinued. It is listed as retired, and GLDAS data now comes through Giovanni.
- The RCM open-data page returned 404, so the entry links to the CSA RADARSAT page instead.

---

## 7. Storage: `.xlsx` instead of a database

**Decision:** `.xlsx` is enough here. The catalog has about 14 rows, and a cached monthly series for 1981–2025 has 540 rows per sample point. Access is mostly reads, and there is one process. **Upgrade path:** reimplement `storage/xlsx_store.py` on PostgreSQL with the same methods, and nothing else changes.

### 7.1 Workbooks

| File | Sheet | Columns |
|---|---|---|
| `catalog.xlsx` | `variables` | id, name, category, units, definition, why_it_matters, example_question, source, seasonal, provider, provider_id, first_year, scale, offset |
| | `demos` | demo_id, title, story, request_json, compare_request_json, narration_steps_json |
| | `resources` | key, step, topics, title, provider, kind, url, how_it_helps, used_in_app, related_json |
| | `meta` | key, value (`seed_version` = `SEED_VERSION+<8-char hash of the column layout>`) |
| `cache.xlsx` | `meta` | cache_key, source, variable_id, lat, lon, resolution, start_year, end_year, fetched_at, n_rows |
| | `series` | cache_key, date, value |
| `analyses.xlsx` | `analyses` | analysis_id, created_at, variable_id, region_json, start_year, end_year, resolution, deseasonalize, alpha, ols_slope_per_decade, ols_p, mk_p, sens_slope_per_decade, significant, verdict, request_json |
| | `series` | analysis_id, date, value, anomaly |

`cache_key = sha1("source|variable|lat,lon|resolution|start|end")[:16]` is **per sample point**, so overlapping regions reuse the same fetches.

### 7.2 Rules (`XlsxStore`)

1. **Only `storage/xlsx_store.py` touches `.xlsx`.**
2. Every write follows the same steps: take a `filelock.FileLock("<file>.lock")`, write `<name>.tmp.xlsx`, then `os.replace()` it over the original. The replace is atomic on Windows and Linux.
3. Async callers use the `a*` wrappers, which run the IO in `asyncio.to_thread`. A `threading.Lock` serializes access to the in-memory state.
4. The cache workbook is loaded once into memory, and reads are served from memory. One analysis's new series are written in a **single** workbook rewrite.
5. **Daily series are cached in memory only**, up to 200 entries, because they have too many rows for a spreadsheet.
6. A workbook that can't be read is renamed to `*.corrupt-<timestamp>.xlsx` and treated as empty.
7. uvicorn must run with **1 worker**.
8. On Windows, an `.xlsx` that is open in Excel is locked, so close it while the server runs.

---

## 8. Processing pipeline (`services/analysis.py::run_analysis`)

```
AnalyzeRequest (pydantic-validated)
  → variable lookup (404)
  → region.sample_points(): point → 1 point; bbox → evenly spaced cell centres at ~1° step,
        max 5×5 = 25 (monthly) or 2×2 = 4 (daily); weights = cos(lat), normalised
  → series.regional_series(): cache hits from XlsxStore; misses fetched concurrently from NASA POWER;
        new series written to cache in one batch; NaN-aware weighted mean on a complete date index
  → daily? → to_monthly() (a month needs ≥ 50 % valid days)
  → missing_fraction > 20 % → 422
  → convert_units(): optional display unit, value × factor + offset (§5.5)
  → trend.analyze_series()  (§9)
  → explain.build_verdict() + build_hints()
  → save to analyses.xlsx (if save) → AnalyzeResponse
```

---

## 9. Statistics (`services/trend.py`, pure functions)

Let `y_t` be the monthly series and `x_t` the mid-month decimal year, e.g. Jan 2000 = 2000.0417.

1. **Deseasonalize** (default on): `a_t = y_t − mean(y for that calendar month)`. The tests then run on `a_t`.
2. **OLS:** compute `β₁` (slope per year), the residuals, `σ² = SSE/(n−2)` and `Sxx = Σ(x − x̄)²`.
   - **Autocorrelation correction:**
     - lag-1 autocorrelation `r₁` of the residuals
     - effective sample size `n_eff = n(1 − r₁)/(1 + r₁)` when `r₁ > 0`, kept within [3, n]
     - degrees of freedom `df = n_eff − 2`
   - Standard error: `SE = sqrt(σ²/Sxx) · sqrt((n−2)/df)`.
   - Significance: `t = β₁/SE`, with a two-sided p-value from Student's t on `df`.
   - Slope CI: `β₁ ± t₍₁₋α/2, df₎ · SE`, reported per decade.
   - Band around the fitted mean: `ŷ(x) ± t · sqrt(σ²(1/n + (x − x̄)²/Sxx)) · sqrt((n−2)/df)`.
3. **Mann-Kendall** (`pymannkendall`):
   - Deseasonalized data use `hamed_rao_modification_test`, which is robust to autocorrelation. If that returns a non-finite p, the code falls back to `original_test`. Sen's slope is per month, so it is multiplied by 120 to get per decade.
   - Raw (not deseasonalized) data use `seasonal_test(period=12)`. Sen's slope is per year, so it is multiplied by 10.
4. **Derived values:**
   - `total_change = β₁ · years`.
   - `percent_change` is computed only for ratio-scale variables, i.e. not T2M, T2M_MAX or T2M_MIN.
   - `significant = (p_ols < α) and (p_mk < α)`.
5. **Hints** cover: periods under 20 years, results that aren't significant for periods under 30 years, seasonal variables with deseasonalizing turned off, more than 10 % missing data, `n_eff < 0.3 n`, significant trends with small R², daily data having been aggregated, and "try another region".

Verified live on 1981–2025 data:

| Region | Variable | Result |
|---|---|---|
| Interior Alaska | T2M | +0.44 °C/decade, p < 0.001 |
| Central Sahel | PRECTOTCORR | +0.13 mm/day/decade, p < 0.001 |
| Arizona | PRECTOTCORR | −0.080 mm/day/decade, p = 0.003 |

The Sahel and Arizona results trend in opposite directions, which is what the comparison demo shows.

---

## 10. Frontend (`frontend/`)

The scripts load in this order, each adding to `window.ETD`: `config` → `api` → `map` → `charts` → `wizard` → `demos` → `app`.

| File | Role |
|---|---|
| `config.js` | Picks `API_BASE`. On localhost/127.0.0.1 with a port other than 8000 (Live Server) it uses `http://127.0.0.1:8000`; otherwise it uses `""`, which means same origin: FastAPI static or the Netlify proxy. |
| `api.js` | `fetch` wrappers with a 180 s timeout and friendly errors. Downloads exports via a Blob. |
| `map.js` | Leaflet with OSM tiles (`tile.openstreetmap.org`). Point mode places a marker on click. Box mode uses Leaflet.draw rectangles, shrinks boxes over 5° and rejects boxes that cross the dateline. A second blue box is drawn for comparison demos. |
| `charts.js` | Plotly chart with the 95 % band, the monthly data, a 12-month running mean and the trend line. When the raw view is shown, the trend line is shifted to the data mean. Colors follow the page theme. Uses Okabe-Ito colors (orange = main region, blue = comparison). |
| `wizard.js` | What/Where/When form (clicked points and drawn boxes are named via `/api/locations/reverse`; cached, newest click wins; Investigate waits up to 3 s for a pending name): variables grouped by category, definition card, unit picker, place search, idea chips, validation (≥ 10 years, ≤ last complete year), `fill()` for demos. `regionLabel()` formats coordinates with N/S/E/W like the backend. |
| `demos.js` | Narrated, step-by-step demos. When there is a `compare_request`, both analyses run in parallel. |
| `app.js` | State, result cards, verdict and hints, comparison panel, weather card (optional, never blocks), backend status indicator, export buttons, stale-results tracking (below). |

**Desktop layout (> 900 px):**
- The sidebar is a flex column with `position: sticky`, and it scrolls on its own (`overflow-y: auto`). It runs from 16 px below the header to the **bottom edge of the window** (`height: calc(100vh - var(--topbar-h) - 16px)`; no bottom border or radius). A literal `height: 100%` would take the grid row's height (the whole right column) and break the sticky behaviour.
- `app.js` measures `--topbar-h` with a `ResizeObserver`, because the header wraps on narrow windows.
- The page footer lives at the end of the right column (`.content`), and `.layout` has no bottom padding on desktop. A sticky box can't extend past the end of its container, so this lets the sidebar reach the window bottom even when scrolled to the end.
- `index.html` loads CSS and JS with `?v=YYYYMMDD`. Bump it when they change, so browsers and the `:8000` static mount don't serve stale copies.
- The Investigate button (and form errors) sit in `.investigate-dock`, the last item in the sidebar, after the weather card:
  - **Short content:** `margin-top: auto` pins it to the bottom and fills the empty space.
  - **Overflowing content:** the margin is 0, and `position: sticky; bottom` keeps the button visible.
- **Phones (one column):** normal page flow.

**Stale results:** analyses are **not** re-run automatically, because each run downloads up to 25 NASA series and can take a minute. Instead:
- `app.js` keeps `canonical(request)` of the shown results: a fixed-order fingerprint with rounded coordinates that ignores the region name.
- On any input or change in the sidebar, and on map/region and unit changes, `checkDirty()` compares it with the current form.
- When they differ, a fixed **"Update investigation"** bar appears at the bottom of the screen, the results dim (`.results.stale`), and the sidebar button reads "🔄 Update investigation".
- The bar hides while loading and when the form matches the shown results again.

Note: `[hidden] { display: none !important; }` in `styles.css` is required, because components with `display: flex` would otherwise override the `hidden` attribute.

---

## 11. Local development

1. `python -m venv .venv`, then `pip install -r requirements.txt`, and create `.env` from `.env.example`.
2. `cd backend && uvicorn app.main:app --reload --port 8000`.
3. In VS Code, right-click `frontend/index.html` and choose **Open with Live Server** (http://127.0.0.1:5500). `.vscode/settings.json` sets Live Server's root to `/frontend`. It also tells Live Server to ignore `data/**`, `backend/**` and `**/*.xlsx`; without that, every cache write would reload the page.
4. As an alternative, FastAPI also serves `frontend/` at http://127.0.0.1:8000/ (StaticFiles mounted after `/api`).

## 12. Deployment (GitHub → Render + Netlify)

- **Render** (`render.yaml`, New → Blueprint):
  - build: `pip install -r requirements.txt`
  - start: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`
  - `PYTHON_VERSION=3.12.8`
  - `WEATHERAPI_KEY` entered in the dashboard (`sync: false`)
  - health check: `/api/variables`

  On the free plan the service sleeps after idling (cold start of about 1 minute) and its disk is ephemeral. The cache and analyses reset; the catalog is rebuilt at startup.
- **Netlify** (`netlify.toml`): `publish = "frontend"` with no build command, plus the rewrite `/api/*` → `https://YOUR-RENDER-SERVICE.onrender.com/api/:splat` (status 200, force). **Replace the placeholder before deploying.** Because of the proxy the browser stays same-origin, so no CORS setup is needed.

## 13. Error handling and logging

- Upstream problems become `UpstreamError` (502) or `UpstreamTimeout` (504), and bad data becomes `DataQualityError` (422). All are mapped in `main.py`.
- The access-log middleware records the method, **path only**, status and duration.
- The frontend shows every error in the red box under **Investigate**. A failure of the weather card is silent.

## 14. Testing

| File | Covers |
|---|---|
| `test_trend.py` | Synthetic series (known slope + seasonal sine + AR(1) noise): slope recovery, significance, sign, seasonal MK, gaps, n_eff, percent rule |
| `test_nasa_power.py` | Month 13 dropped, −999 → NaN, daily keys, retry on 503, no retry on 4xx (respx) |
| `test_next_steps.py` | Every resource has a workflow step and valid links; suggestions for temperature, not-significant results, satellite runoff and Canadian regions; Canada box test; `/api/resources` relationships and `/api/resources/steps` |
| `test_places.py` | Haversine distance, place labels (same cell / near / ≈ km from / area around), USA shortening, 120-char cap, `/api/locations/reverse` (mocked) and 404, verdict uses the place name |
| `test_region.py` | Hemisphere formatting (S/W instead of minus signs, 0° and 180° without a letter), point/box/named labels, verdict for a southern-western box |
| `test_units.py` | Known conversions (0 °C → 32 °F, 101.325 kPa → 29.92 inHg, …), unknown unit rejected, option keys match catalog units, `/api/variables` options, °F analysis: slope ×1.8 with identical p-values, °F verdict, export columns in °F, invalid unit 422 |
| `test_xlsx_store.py` | Catalog round trip (including resource links), cache persistence across instances, TTL, daily kept in memory, corrupt-file recovery, saved analyses |
| `test_api.py` | Full API through `TestClient` with mocked upstreams: analyze → cache hit → reload → xlsx/csv export, bbox sampling, validation (422), 404s, 502 mapping, all-missing 422, search/weather, CORS for :5500 |

| `test_giovanni.py` | CSV parsing with metadata and fill values, daily → monthly, sign-in flow (Basic auth sent only to Earthdata, token cached), unit conversion, rejected-login message, variables unavailable without a login, first-year and daily 422s, end-to-end Giovanni analysis (3 × 3 points), `/api/resources` |

Commands: `pytest -q` (66 tests, no network) and `ruff check .`.

## 15. Four-day schedule

| Day | Focus |
|---|---|
| 1 | ✅ Backend, statistics, storage, tests, dashboard (done) |
| 2 | Deploy to Render + Netlify; test on phones; tune demo narration |
| 3 | Extra variables/regions, compare mode for any two regions, polish copy |
| 4 | Pitch video, screenshots, README team section, final checks |

## 16. Data citations

- NASA POWER: "These data were obtained from the NASA Langley Research Center (LaRC) POWER Project funded through the NASA Earth Science/Applied Science Program." Meteorology from MERRA-2 (NASA GMAO).
- NASA Giovanni: "Analyses and visualizations used in this study were produced with the Giovanni online data system, developed and maintained by the NASA GES DISC."
- Current weather and geocoding: WeatherAPI.com. Map tiles: © OpenStreetMap contributors.
