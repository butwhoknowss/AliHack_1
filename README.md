# 🌍 Earth Trend Detective

**Become a data detective for planet Earth.** Pick something to measure (temperature, rainfall, soil moisture, sunlight…), pick a place on the map, and find out:

- **What** is changing?
- **Where** is it changing?
- **How much** is it changing (per decade, and in total)?
- **Is the change "significant"**, or could it just be natural ups and downs?

Built for high-school and college students and the curious public. It uses NASA Earth science data (NASA POWER, based on the MERRA-2 reanalysis) from 1981 to the last complete year.

---

## Features

- 🔎 **Variable catalog with plain-English definitions**: 11 variables, each with its units and why it matters.
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
pytest -q          # 29 tests, no internet needed (all services are mocked)
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
2. **Render:** sign in with GitHub, then go to **New → Blueprint** and pick this repo. Render reads `render.yaml`. When asked, enter your `WEATHERAPI_KEY`. After the deploy, note the URL, e.g. `https://earth-trend-detective-api.onrender.com`.
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
| [NASA POWER](https://power.larc.nasa.gov/) | Long-term monthly and daily time series (1981 to the last complete year) | Meteorology from **MERRA-2** (NASA GMAO), radiation from CERES/FLASHFlux. No key needed. |
| [WeatherAPI.com](https://www.weatherapi.com/) | Place search and current conditions | Needs a key in `.env`. Its free history only covers the last few days, so it is **not** used for trends. |

Citation: *"These data were obtained from the NASA Langley Research Center (LaRC) POWER Project funded through the NASA Earth Science/Applied Science Program."*

---

## Tech stack

FastAPI · uvicorn · pandas · statsmodels / scipy · pymannkendall · openpyxl (**.xlsx storage, no database**) · Leaflet · Plotly · Netlify (frontend) · Render (backend).

Full design: **[Architecture.md](Architecture.md)**. Notes for contributors and AI assistants: **[CLAUDE.md](CLAUDE.md)**.

---

## Limitations

- Only linear trends are tested. Non-linear changes and sudden jumps are not modeled.
- Region boxes are limited to 5° × 5° and averaged from up to 25 sample points (4 for daily data).
- NASA POWER is a gridded reanalysis/satellite product with cells about 50 km across, not station measurements.
- Statistical significance ≠ cause. A significant trend tells you *something* is changing, not *why*.

## Team

_Add team members and roles here._
