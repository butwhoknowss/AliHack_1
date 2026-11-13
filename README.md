# 🌍 Earth Trend Detective

**Become a data detective for planet Earth.** Pick something to measure (temperature, rainfall, soil moisture, sunlight…), pick a place on the map, and find out:

- **What** is changing?
- **Where** is it changing?
- **How much** is it changing (per decade, and in total)?
- **Is the change "significant"**, or could it just be natural ups and downs?

Built for high-school and college students and the curious public. It uses NASA Earth science data:
- **NASA POWER** (based on the MERRA-2 reanalysis), from 1981 to the last complete year
- satellite and land-model data through **NASA Giovanni** (GPM, OMI, AIRS, GLDAS), from 2000–2005 onward

---

## Features

- 🔎 **Variable catalog with plain-English definitions**: 11 NASA POWER variables, plus 6 🛰️ satellite variables from NASA Giovanni (GPM, OMI, AIRS, GLDAS). Each has its units, start year and why it matters.
- 📚 **Resources panel** with the challenge's official NASA, NOAA, KNMI and CSA tools and guides. It is organised as a detective workflow (get data → test → cross-check → explain) and shows how the resources connect.
- 🔗 **Next steps for each case:** after an analysis, the resources that fit your variable, place and result, each with a reason.
- 🗺️ **Pick any region**: click a point, draw a box (up to 5° × 5°), search a place name, or use the quick ideas (desert, rainforest, Arctic, big city).
- 📈 **Interactive time series**: raw values or anomalies with the seasonal cycle removed, a 12-month running mean, the trend line, and a 95 % confidence band.
- 🧮 **Trend statistics**:
  - rate of change per decade and total change
  - linear-regression **t-test** with a **95 % confidence interval**, corrected for autocorrelation
  - **Mann-Kendall** test with **Sen's slope**
- ✅ **Plain-language verdict**: "significant", "mixed evidence", or "not significant yet", plus hints on what to try next.
- 🎬 **3 guided demos**:
  - Is Interior Alaska warming?
  - Is the Sahel getting wetter?
  - Same variable, opposite directions: Sahel vs. Arizona rainfall
- ☀️ **Current weather card** for the chosen place (WeatherAPI.com).
- 💾 **Export** any analysis to Excel (.xlsx) or CSV.

---

## Run it on your computer (VS Code + Live Server)

You need **Python 3.12 or newer** and the VS Code **Live Server** extension.

### 1. One-time setup

```bash
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env` in the project folder (copy `.env.example`) and set your WeatherAPI.com key:

```
WEATHERAPI_KEY=your-key-here
```

`.env` is gitignored, so **never commit it**. NASA POWER needs no key.

### 2. Start the backend

**Easiest (Windows):** double-click **`start-backend.bat`** in the project folder and **keep its window open**. The first time, it creates `.venv` and installs the packages for you.

Or in a terminal:

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

API docs: http://127.0.0.1:8000/docs. To stop the backend, press **Ctrl+C** in its window, or close the window.

> A web page can't start Python by itself, so the dashboard only works while this backend window is open. If you open the page first, it shows "backend offline — retrying…" and connects automatically as soon as you start the backend.

### 3. Open the dashboard

Right-click **`frontend/index.html`** → **Open with Live Server**. It opens at http://127.0.0.1:5500 and talks to the backend on port 8000 automatically.

> The project's `.vscode/settings.json` sets Live Server's root to `frontend/`. It also stops Live Server from reloading the page every time the backend writes its Excel cache files.
>
> No Live Server? Open http://127.0.0.1:8000/ instead, because the backend serves the dashboard too.

### 4. Run the tests

```bash
pytest -q          # 51 tests, no internet needed (all services are mocked)
ruff check .       # lint
```

---

## Deploy (GitHub → Render + Netlify)

Netlify only hosts static files, so the app is split across two services. You can sign in to **both with your GitHub account**.

| Part | Host | What it runs |
|---|---|---|
| Dashboard (`frontend/`) | **Netlify** | static HTML/CSS/JS |
| API (`backend/`) | **Render** (free web service) | FastAPI + uvicorn |

1. **Push this repo to GitHub.** `.env` stays on your computer.
2. **Render:** sign in with GitHub, then go to **New → Blueprint** and pick this repo. Render reads `render.yaml`. When asked, enter your `WEATHERAPI_KEY`, plus `EARTHDATA_USERNAME` and `EARTHDATA_PASSWORD` if you want the satellite variables. After the deploy, note the URL, e.g. `https://earth-trend-detective-api.onrender.com`.
3. **Edit `netlify.toml`:** replace `YOUR-RENDER-SERVICE` with your Render service name. Commit and push.
4. **Netlify:** sign in with GitHub, then go to **Add new site → Import from Git** and pick this repo. `netlify.toml` already sets the publish folder (`frontend`) and forwards `/api/*` to Render. No build command is needed.

Things to know about the free Render plan:
- **Cold starts:** the server sleeps after about 15 minutes of no use, so the first request can take up to a minute. The dashboard shows a "still working…" message while it waits.
- **Temporary disk:** the Excel cache and saved analyses are wiped when the server restarts. The variable catalog is rebuilt automatically, so the app keeps working.

---

## How to use it

1. **What?** Choose a variable, e.g. *Air temperature (2 m)*, and read its definition card.
2. **Where?** Search "Fairbanks", click the map, draw a box, or click an idea chip.
3. **When?** Choose at least **10 years**; 30+ years is better.
4. Press **🔍 Investigate** and read the chart, the five result cards and the verdict.
5. Try the same variable in another region. It can trend **up in one place and down in another**, even when the same process drives both.

---

## What does "significant" mean?

Climate data wiggle up and down naturally. A trend is **statistically significant** when it is very unlikely (usually less than a 5 % chance, *p < 0.05*) that random wiggles alone would produce a trend that strong.

| Test | Idea | Good at |
|---|---|---|
| **Linear regression t-test** | Fits a straight line and checks whether its slope is clearly different from zero. Also gives a **95 % confidence interval**. | Measuring *how much* per decade |
| **Mann-Kendall** (+ Sen's slope) | Asks how often later values are higher than earlier ones. It doesn't assume a straight line or bell-curve noise. | A robust "is it really going up or down?" check |

- **Both tests agree:** significant.
- **Only one agrees:** mixed evidence.
- **Neither agrees:** not significant *yet*. Sometimes a trend only becomes significant with a longer record.

Before testing, the app (by default) **removes the seasonal cycle**. Otherwise "summer is hotter than winter" hides the long-term change.

---

## Data sources

| Source | Used for | Notes |
|---|---|---|
| [NASA POWER](https://power.larc.nasa.gov/) | 11 variables, monthly or daily, from 1981 to the last complete year | Meteorology from **MERRA-2** (NASA GMAO), radiation from CERES/FLASHFlux. No key needed. |
| [NASA Giovanni](https://giovanni.gsfc.nasa.gov/giovanni/) | 6 satellite and land-model variables (monthly) | GPM rainfall, OMI aerosols and ozone, AIRS temperature, GLDAS evaporation and runoff. **Needs a free NASA Earthdata login** (see below). Without one, these variables show as disabled. |
| [WeatherAPI.com](https://www.weatherapi.com/) | Place search and current conditions | Needs a key in `.env`. Its free history only covers the last few days, so it is **not** used for trends. |

Citations:
- *"These data were obtained from the NASA Langley Research Center (LaRC) POWER Project funded through the NASA Earth Science/Applied Science Program."*
- *"Analyses and visualizations used in this study were produced with the Giovanni online data system, developed and maintained by the NASA GES DISC."*

### The satellite variables

All six were checked against the live Giovanni API.

| Variable | Instrument / model | Units | Data from |
|---|---|---|---|
| Rainfall measured by satellite (GPM IMERG) | GPM IMERG | mm/day | 2001 |
| Haze / aerosols in the air (OMI) | Aura OMI | AOD (no units) | 2005 |
| Total ozone column (OMI) | Aura OMI | DU | 2005 |
| Surface air temperature from space (AIRS) | Aqua AIRS | °C | 2003 |
| Evaporation + plant transpiration (GLDAS) | GLDAS Noah | mm/day | 2000 |
| Surface runoff (GLDAS): the closest thing to streamflow | GLDAS Noah | mm/day | 2000 |

### Turning on the satellite variables (NASA Giovanni)

1. Create a free account at https://urs.earthdata.nasa.gov/users/new.
2. In your Earthdata profile, under **Applications → Authorized Apps**, approve **NASA GESDISC DATA ARCHIVE**. If you are asked to approve anything for Giovanni, accept that too.
3. Add these lines to `.env`, then restart the backend (close and reopen `start-backend.bat`):
   ```
   EARTHDATA_USERNAME=your-username
   EARTHDATA_PASSWORD=your-password
   ```
   - Quotes around the password are fine.
   - Use your username and password, not a token. Giovanni rejected an Earthdata "Generate Token" token sent on its own. `EARTHDATA_TOKEN` is only tried if no username or password is set.
4. Hover over the **● online** status (top right). It should say "NASA Giovanni: ok", and the 🛰️ variables become selectable.

**If it still says "not working"**, the tooltip and the greyed-out variable's warning show the exact reason:

| Message | What to do |
|---|---|
| "Earthdata rejected EARTHDATA_USERNAME/EARTHDATA_PASSWORD" | Check the spelling in `.env`. |
| "Earthdata showed a login/approval page" | Do step 2, or log in once at https://giovanni.gsfc.nasa.gov/giovanni/. |
| "does not recognise the data ID" | A data name in `seed.py` is wrong. The login is fine. |

The backend checks the login once at startup, so restart it after changing `.env`. You can also open http://127.0.0.1:8000/api/health and look at `giovanni` and `giovanni_error`.

Notes:
- Giovanni's API only answers for single points, so boxes are averaged from up to 9 points. That makes box analyses a bit slower than NASA POWER.
- Satellite variables are monthly only. Each has its own start year (2000–2005), and the form adjusts the start year for you.
- The app signs in to Giovanni for you and keeps the sign-in for about a day, then renews it. Your password is only sent to NASA's Earthdata login server (`urs.earthdata.nasa.gov`).
- MODIS aerosol data isn't offered by Giovanni's API, so haze comes from OMI instead.

## Resources & learn more

The challenge's 13 official resources aren't a random list: together they cover every step of a trend investigation. The dashboard's **📚 Resources & learn more** panel groups them by step. Each resource also says which other resources it **connects to** and why; click a link to jump to it.

| Step | Resources | What they do for a detective |
|---|---|---|
| **1 · Get the data** | NASA Giovanni *(built in)* · Hydrology Time Series *(retired, so its GLDAS data now comes through Giovanni)* · AppEEARS | Turn satellite data for a place into a time series |
| **2 · Test the trend** | Trend-tests article · Statistical significance guide · SeaWiFS chlorophyll paper (Acker et al., 2009) | How significance tests work, plus a NASA study that used the same recipe as this app |
| **3 · Cross-check** | NOAA Climate Data Online (station records) · KNMI Climate Explorer | Confirm a finding with independent data |
| **4 · Explain and go further** | CSA: RADARSAT Constellation Mission · SWOT · Geo.ca · Ecosystem monitoring · SAR Python tutorial | Why the change matters, and Canadian data and missions |

Some of the connections:
- **Giovanni replaced the Hydrology Time Series tool** for GLDAS water data. The SeaWiFS paper built its time series in Giovanni too.
- **AppEEARS fills a gap:** it gives fine-resolution MODIS land data, which Giovanni's API does not serve.
- **CDO and KNMI** are two independent ways to check a trend.
- **RCM, the SAR tutorial, the ecosystems page and Geo.ca** form one Canadian chain: the radar satellites, how to use their images, what they monitor, and where to find Canadian data.
- **SWOT** measures river and lake heights directly. Its record only started in 2022, so it can't show a 10-year trend yet, which makes it a good lesson in record length.

### 🔗 Next steps for each case

After every investigation, the verdict panel suggests up to 4 of these resources, with a reason written for your result:

| Your case | Suggestion |
|---|---|
| Temperature or rainfall | Compare with real weather stations near your region (NOAA CDO) |
| "Not significant yet" | The significance guide: why that doesn't prove nothing is changing |
| The two tests disagree | The trend-tests article: how they differ |
| Satellite variable | Open Giovanni to map the whole region |
| Soil moisture or evaporation | AppEEARS, to see if the vegetation responds |
| Runoff | SWOT, which can confirm it in future |
| A region in or near Canada | Geo.ca and RCM |

The resources and their links live in `backend/app/storage/seed.py` (`RESOURCES`, `RESOURCE_STEPS`). The suggestion rules are in `backend/app/services/next_steps.py`.

---

## Tech stack

FastAPI · uvicorn · pandas · statsmodels / scipy · pymannkendall · openpyxl (**.xlsx storage, no database**) · Leaflet · Plotly · Netlify (frontend) · Render (backend).

Full design: **[Architecture.md](Architecture.md)**. Notes for contributors and AI assistants: **[CLAUDE.md](CLAUDE.md)**.

---

## Limitations

- Only linear trends are tested. Non-linear changes and sudden jumps are not modeled.
- Region boxes are limited to 5° × 5°. They are averaged from up to 25 sample points (4 for daily data, 9 for satellite variables).
- NASA POWER is a gridded reanalysis/satellite product with cells about 50 km across, not station measurements.
- Satellite records start in 2000–2005, so their trends cover about 20–25 years. A real change may not reach "significant" yet.
- The satellite variables depend on NASA Giovanni being online and on a working Earthdata login.
- Statistical significance ≠ cause. A significant trend tells you *something* is changing, not *why*.

## Team

_Add team members and roles here._
