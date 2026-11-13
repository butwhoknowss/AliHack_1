"""Default content for data/catalog.xlsx (created on startup if missing).

To change the catalog: edit this file, bump SEED_VERSION and restart the API —
data/catalog.xlsx is rebuilt automatically when its stored version differs.
"""

from pathlib import Path

from .xlsx_store import CATALOG_FILE, CATALOG_SCHEMA, read_catalog_version, write_catalog

POWER_SOURCE = "NASA POWER (MERRA-2 reanalysis)"
POWER_RAD_SOURCE = "NASA POWER (CERES / FLASHFlux satellite radiation)"

VARIABLES: list[dict] = [
    {
        "id": "T2M",
        "name": "Air temperature (2 m)",
        "category": "Atmosphere",
        "units": "°C",
        "definition": "How warm the air is about 2 metres above the ground — roughly where people feel it. Monthly values are averages of every hour in the month.",
        "why_it_matters": "Rising air temperature is the most direct sign of a warming climate and affects crops, health, ice and ecosystems.",
        "example_question": "Is the Arctic warming faster than the tropics?",
        "source": POWER_SOURCE,
        "seasonal": True,
    },
    {
        "id": "T2M_MAX",
        "name": "Daily maximum temperature",
        "category": "Atmosphere",
        "units": "°C",
        "definition": "The hottest temperature reached each day, 2 metres above the ground. Monthly values average these daily highs.",
        "why_it_matters": "Hotter afternoons mean more heat stress for people, animals and crops.",
        "example_question": "Are summer afternoons in my city getting hotter?",
        "source": POWER_SOURCE,
        "seasonal": True,
    },
    {
        "id": "T2M_MIN",
        "name": "Daily minimum temperature",
        "category": "Atmosphere",
        "units": "°C",
        "definition": "The coldest temperature reached each day (usually just before sunrise), 2 metres above the ground.",
        "why_it_matters": "Warmer nights reduce frost, change growing seasons and keep cities from cooling down during heat waves.",
        "example_question": "Are nights warming faster than days?",
        "source": POWER_SOURCE,
        "seasonal": True,
    },
    {
        "id": "PRECTOTCORR",
        "name": "Precipitation",
        "category": "Water cycle",
        "units": "mm/day",
        "definition": "Rain plus melted snow reaching the ground, shown as the average millimetres per day. 1 mm means 1 litre of water on each square metre.",
        "why_it_matters": "Changes in rainfall drive floods, droughts, water supply and farming.",
        "example_question": "Is the Sahel getting wetter or drier?",
        "source": POWER_SOURCE,
        "seasonal": True,
    },
    {
        "id": "RH2M",
        "name": "Relative humidity (2 m)",
        "category": "Water cycle",
        "units": "%",
        "definition": "How close the air is to being saturated with water vapour (100 % = fully saturated, fog or dew forms).",
        "why_it_matters": "Humidity affects how hot it feels, plant water loss and fire risk.",
        "example_question": "Is the air over a desert getting drier?",
        "source": POWER_SOURCE,
        "seasonal": True,
    },
    {
        "id": "QV2M",
        "name": "Specific humidity (2 m)",
        "category": "Water cycle",
        "units": "g/kg",
        "definition": "The actual amount of water vapour in the air: grams of water per kilogram of air.",
        "why_it_matters": "Warmer air can hold more water, so rising moisture is a fingerprint of warming and fuels heavier downpours.",
        "example_question": "Is the air over the rainforest holding more water than before?",
        "source": POWER_SOURCE,
        "seasonal": True,
    },
    {
        "id": "GWETTOP",
        "name": "Surface soil wetness (0–5 cm)",
        "category": "Land",
        "units": "fraction (0–1)",
        "definition": "How wet the top few centimetres of soil are, from 0 (completely dry) to 1 (completely saturated).",
        "why_it_matters": "Surface soil moisture controls seed germination, dust storms and how much rain soaks in versus runs off.",
        "example_question": "Is the topsoil in a farming region drying out?",
        "source": POWER_SOURCE,
        "seasonal": True,
    },
    {
        "id": "GWETROOT",
        "name": "Root-zone soil wetness",
        "category": "Land",
        "units": "fraction (0–1)",
        "definition": "How wet the soil is down to about 1 metre, where most plant roots are, from 0 (dry) to 1 (saturated).",
        "why_it_matters": "Root-zone moisture is the water plants can actually use — a key drought indicator.",
        "example_question": "Is drought becoming more common in a grassland?",
        "source": POWER_SOURCE,
        "seasonal": True,
    },
    {
        "id": "WS2M",
        "name": "Wind speed (2 m)",
        "category": "Atmosphere",
        "units": "m/s",
        "definition": "How fast the air moves 2 metres above the ground, averaged over time.",
        "why_it_matters": "Wind affects evaporation, dust, wind energy and how pollution spreads.",
        "example_question": "Are winds over the plains slowing down?",
        "source": POWER_SOURCE,
        "seasonal": True,
    },
    {
        "id": "ALLSKY_SFC_SW_DWN",
        "name": "Sunlight reaching the surface",
        "category": "Energy",
        "units": "MJ/m²/day",
        "definition": "Solar energy reaching the ground on each square metre per day (in megajoules; 3.6 MJ = 1 kWh), including the dimming effect of clouds and haze.",
        "why_it_matters": "Changes reveal shifts in cloudiness and air pollution and matter for solar power and plant growth.",
        "example_question": "Has air above a big city become clearer or hazier?",
        "source": POWER_RAD_SOURCE,
        "seasonal": True,
    },
    {
        "id": "PS",
        "name": "Surface air pressure",
        "category": "Atmosphere",
        "units": "kPa",
        "definition": "The weight of the air above a place. It is lower on mountains and changes with passing weather systems.",
        "why_it_matters": "Long-term pressure changes reflect shifts in large weather patterns such as storm tracks.",
        "example_question": "Are weather patterns over the ocean shifting?",
        "source": POWER_SOURCE,
        "seasonal": False,
    },
]


for _v in VARIABLES:  # NASA POWER rows: provider id = variable id, data from 1981, no unit conversion
    _v.update(provider="power", provider_id=_v["id"], first_year=1981, scale=1.0, offset=0.0)

GIOVANNI_SOURCE = "NASA Giovanni"

# Giovanni data IDs follow <dataset shortname>_<version>_<variable>.
# Values are converted to friendlier units with value * scale + offset.
GIOVANNI_VARIABLES: list[dict] = [
    {
        "id": "GPM_PRECIP",
        "name": "Rainfall measured by satellite (GPM IMERG)",
        "category": "Water cycle",
        "units": "mm/day",
        "definition": "Rain and snow estimated from the Global Precipitation Measurement (GPM) satellite constellation, which scans clouds with radar and microwave sensors.",
        "why_it_matters": "A satellite-only view of rainfall — compare it with the model-based 'Precipitation' variable to see if they agree.",
        "example_question": "Do satellites and models agree that the Sahel is getting wetter?",
        "source": f"{GIOVANNI_SOURCE} — GPM IMERG monthly (GES DISC)",
        "seasonal": True,
        "provider": "giovanni",
        "provider_id": "GPM_3IMERGM_07_precipitation",
        "first_year": 2001,
        "scale": 24.0,   # mm/hr -> mm/day
        "offset": 0.0,
    },
    {
        "id": "OMI_AOD",
        "name": "Haze / aerosols in the air (OMI)",
        "category": "Air quality",
        "units": "AOD (no units)",
        "definition": "Aerosol optical depth: how much sunlight tiny particles (smoke, dust, pollution, sea salt) block. 0.1 is clean air; above 1 is very hazy. Measured at 500 nm (blue-green light).",
        "why_it_matters": "Tracks air pollution, wildfire smoke and dust storms, which affect health and climate.",
        "example_question": "Is the air above a big city getting cleaner or dirtier?",
        "source": f"{GIOVANNI_SOURCE} — Aura OMI OMAERUVd v003 (GES DISC)",
        "seasonal": True,
        "provider": "giovanni",
        "provider_id": "OMAERUVd_003_FinalAerosolOpticalDepth500",
        "first_year": 2005,
        "scale": 1.0,
        "offset": 0.0,
    },
    {
        "id": "OMI_OZONE",
        "name": "Total ozone column (OMI)",
        "category": "Air quality",
        "units": "DU",
        "definition": "The total amount of ozone in a column of air above a place, measured by the Ozone Monitoring Instrument. 300 Dobson Units would be a 3 mm thick layer of pure ozone.",
        "why_it_matters": "The ozone layer shields us from harmful ultraviolet light; its recovery after the Montreal Protocol is a famous environmental success story.",
        "example_question": "Is the ozone layer recovering over Antarctica or the Arctic?",
        "source": f"{GIOVANNI_SOURCE} — OMI OMTO3d daily, averaged to months (GES DISC)",
        "seasonal": True,
        "provider": "giovanni",
        "provider_id": "OMTO3d_003_ColumnAmountO3",
        "first_year": 2005,
        "scale": 1.0,
        "offset": 0.0,
    },
    {
        "id": "AIRS_TSURF",
        "name": "Surface air temperature from space (AIRS)",
        "category": "Atmosphere",
        "units": "°C",
        "definition": "Air temperature near the surface measured by the Atmospheric Infrared Sounder on NASA's Aqua satellite (daytime overpass).",
        "why_it_matters": "An independent satellite check on warming trends from weather models.",
        "example_question": "Does a satellite see the same Arctic warming as the model data?",
        "source": f"{GIOVANNI_SOURCE} — AIRS AIRS3STM monthly (GES DISC)",
        "seasonal": True,
        "provider": "giovanni",
        "provider_id": "AIRS3STM_7_0_SurfAirTemp_A",
        "first_year": 2003,
        "scale": 1.0,
        "offset": -273.15,  # kelvin -> °C
    },
    {
        "id": "GLDAS_EVAP",
        "name": "Evaporation + plant transpiration (GLDAS)",
        "category": "Water cycle",
        "units": "mm/day",
        "definition": "Water moving from soil, lakes and plant leaves into the air, from NASA's Global Land Data Assimilation System (a land model fed with satellite data).",
        "why_it_matters": "Evapotranspiration links rain, soil moisture, crops and heat — when it changes, the whole water cycle is shifting.",
        "example_question": "Is more water evaporating from farmland as it warms?",
        "source": f"{GIOVANNI_SOURCE} — GLDAS Noah 2.1 monthly (GES DISC)",
        "seasonal": True,
        "provider": "giovanni",
        "provider_id": "GLDAS_NOAH025_M_2_1_Evap_tavg",
        "first_year": 2000,
        "scale": 86400.0,  # kg/m²/s -> mm/day
        "offset": 0.0,
    },
    {
        "id": "GLDAS_RUNOFF",
        "name": "Surface runoff (GLDAS)",
        "category": "Water cycle",
        "units": "mm/day",
        "definition": "Rain and meltwater that flows over the ground into streams instead of soaking in, from the GLDAS land model. It is the closest global stand-in for streamflow.",
        "why_it_matters": "Runoff feeds rivers and floods; trends show whether streams are likely to carry more or less water.",
        "example_question": "Are rivers in a region likely carrying more water than 20 years ago?",
        "source": f"{GIOVANNI_SOURCE} — GLDAS Noah 2.1 monthly (GES DISC)",
        "seasonal": True,
        "provider": "giovanni",
        "provider_id": "GLDAS_NOAH025_M_2_1_Qs_acc",
        "first_year": 2000,
        "scale": 8.0,  # kg/m² per 3 hours -> mm/day
        "offset": 0.0,
    },
]

ALL_VARIABLES = VARIABLES + GIOVANNI_VARIABLES

# Official challenge resources (all URLs checked when added), organised as a detective workflow:
#   key      short id used by `related` and by services/next_steps.py
#   step     data -> test -> check -> explain (the order of the Resources panel)
#   topics   which kinds of variables / places a resource is relevant to
#   related  [[key, why the two resources belong together], ...]
RESOURCE_STEPS: list[dict] = [
    {"step": "data", "title": "1 · Get the data and build a time series",
     "intro": "Tools that turn satellite or model data for a place into a series of values over time."},
    {"step": "test", "title": "2 · Test whether the trend is real",
     "intro": "How significance tests work, and a NASA study that used the same recipe as this app."},
    {"step": "check", "title": "3 · Cross-check with other data",
     "intro": "A good detective confirms a finding with an independent witness: station records or other datasets."},
    {"step": "explain", "title": "4 · Explain the change and go further",
     "intro": "Missions and examples that show why a change matters for water, ice, forests and wetlands."},
]
RESOURCES: list[dict] = [
    {"key": "giovanni", "step": "data", "topics": "atmosphere,water,air,land",
     "related": [['hydrology', 'Giovanni now serves the GLDAS hydrology data that the retired Hydrology Time Series tool used to provide.'], ['seawifs', 'The SeaWiFS study built its chlorophyll time series with Giovanni.'], ['appeears', "For finer-resolution land data (such as MODIS vegetation), which Giovanni's API does not serve."]],
     "title": "Giovanni", "provider": "NASA", "kind": "Data tool", "used_in_app": True,
     "url": "https://giovanni.gsfc.nasa.gov/giovanni/",
     "how_it_helps": "Built into this app: it supplies the satellite variables (GPM, OMI, AIRS, GLDAS). Open it to make maps and area-averaged time series."},
    {"key": "hydrology", "step": "data", "topics": "water",
     "related": [['giovanni', 'Its successor for GLDAS evaporation and runoff time series.'], ['swot', 'Modelled runoff and flow (GLDAS) vs. water heights measured directly from space (SWOT).']],
     "title": "Hydrology Time Series (Data Rods)", "provider": "NASA", "kind": "Data tool", "used_in_app": False,
     "url": "https://disc.gsfc.nasa.gov/information/tools?title=Hydrology%20Data%20Rods",
     "how_it_helps": "NASA has retired this service; we get the same GLDAS hydrology data (evaporation, runoff) through Giovanni instead."},
    {"key": "appeears", "step": "data", "topics": "land",
     "related": [['giovanni', 'Giovanni gives coarse, long climate series; AppEEARS gives fine land detail for the same place.'], ['ecosystems', 'Vegetation and land-cover change is how satellites track the ecosystems on that page.']],
     "title": "AppEEARS", "provider": "NASA", "kind": "Data tool", "used_in_app": False,
     "url": "https://appeears.earthdatacloud.nasa.gov/",
     "how_it_helps": "Extract fine-resolution land data (e.g. MODIS vegetation greenness) for your own points — useful when a 50 km grid cell is too coarse."},
    {"key": "cdo", "step": "check", "topics": "atmosphere,water",
     "related": [['knmi', "KNMI Climate Explorer can also analyse station series, so you can test a station's trend too."], ['trendtests', 'Use the same tests on a station series.']],
     "title": "Climate Data Online (CDO)", "provider": "NOAA", "kind": "Data tool", "used_in_app": False,
     "url": "https://www.ncei.noaa.gov/cdo-web/",
     "how_it_helps": "Real weather-station records. Compare a station's trend with the gridded trend this app finds nearby."},
    {"key": "seawifs", "step": "test", "topics": "statistics,water",
     "related": [['giovanni', 'The data tool the study used to build its time series.'], ['trendtests', 'Explains the kind of trend tests the study applies.']],
     "title": "Time-Series Analysis of SeaWiFS Chlorophyll in River-Influenced Coastal Regions (Acker et al., 2009)", "provider": "NASA", "kind": "Article", "used_in_app": False,
     "url": "https://ntrs.nasa.gov/api/citations/20090042747/downloads/20090042747.pdf",
     "how_it_helps": "A research example of the same recipe this app uses: build monthly series in Giovanni, remove seasons, then test significance."},
    {"key": "knmi", "step": "check", "topics": "atmosphere,water,air,land",
     "related": [['cdo', 'Station records are an independent check on gridded data.'], ['giovanni', 'Compare its datasets with the satellite series used here.']],
     "title": "KNMI Climate Explorer", "provider": "KNMI", "kind": "Data tool", "used_in_app": False,
     "url": "https://climexp.knmi.nl/",
     "how_it_helps": "A research-grade tool to double-check a trend you found here with other datasets and methods."},
    {"key": "trendtests", "step": "test", "topics": "statistics",
     "related": [['significance', 'Start there if p-values are new to you.'], ['seawifs', 'See trend tests used in a real NASA study.']],
     "title": "Statistical test methods to detect trends in time series", "provider": "Statistics guides", "kind": "Article", "used_in_app": False,
     "url": "https://vlyubchich.r-universe.dev/funtimes/doc/trendtests.html",
     "how_it_helps": "Explains the t-test and Mann-Kendall test used here, and why autocorrelation matters."},
    {"key": "significance", "step": "test", "topics": "statistics",
     "related": [['trendtests', 'The next step: tests made specifically for trends over time.']],
     "title": "A Comprehensive Guide to Statistical Significance", "provider": "Statistics guides", "kind": "Article", "used_in_app": False,
     "url": "https://statsig.com/perspectives/a-comprehensive-guide-to-statistical-significance",
     "how_it_helps": "A friendly introduction to p-values and what 'significant' does (and does not) mean."},
    {"key": "rcm", "step": "explain", "topics": "canada,water,land",
     "related": [['sar', 'The tutorial teaches how to open and map RADARSAT radar images.'], ['ecosystems', "Ecosystem monitoring is one of RCM's three main jobs."], ['geo', 'Canadian open geospatial data to put radar images in context.']],
     "title": "RADARSAT Constellation Mission (RCM)", "provider": "CSA", "kind": "Mission", "used_in_app": False,
     "url": "https://www.asc-csa.gc.ca/eng/satellites/radarsat/",
     "how_it_helps": "Radar satellites that see through clouds, day or night — used for sea ice, oil spills, floods, wetlands and crops."},
    {"key": "geo", "step": "explain", "topics": "canada",
     "related": [['rcm', "Canada's own radar satellites watch the same regions."], ['ecosystems', 'Environmental issues you can explore with Canadian data.']],
     "title": "Geo.ca", "provider": "CSA", "kind": "Data tool", "used_in_app": False,
     "url": "https://geo.ca/",
     "how_it_helps": "Canada's open geospatial data — handy for Canadian regions you investigate here."},
    {"key": "swot", "step": "explain", "topics": "water",
     "related": [['hydrology', 'Measured water heights vs. modelled runoff and river flow.'], ['significance', 'Why a 2–3 year record cannot show a significant trend yet.']],
     "title": "SWOT mission", "provider": "CSA", "kind": "Mission", "used_in_app": False,
     "url": "https://www.asc-csa.gc.ca/eng/satellites/swot.asp",
     "how_it_helps": "A NASA-CNES mission with CSA and UK partners that measures water heights of lakes, rivers and oceans. It launched in December 2022, so its record is still too short for a 10-year trend test — a good example of why record length matters."},
    {"key": "ecosystems", "step": "explain", "topics": "land,water,canada",
     "related": [['rcm', 'The radar mission behind many of these examples.'], ['appeears', 'Get vegetation data to investigate an ecosystem yourself.']],
     "title": "Monitoring and protecting our ecosystems from space", "provider": "CSA", "kind": "Article", "used_in_app": False,
     "url": "https://www.asc-csa.gc.ca/eng/satellites/everyday-lives/monitoring-and-protecting-our-ecosystems-from-space.asp",
     "how_it_helps": "Real examples of satellites tracking forests, wetlands and protected areas."},
    {"key": "sar", "step": "explain", "topics": "canada",
     "related": [['rcm', 'RCM is the newest generation of the RADARSAT satellites used in the tutorial.']],
     "title": "Synthetic Aperture Radar Python tutorial (RADARSAT-1)", "provider": "CSA", "kind": "Tutorial", "used_in_app": False,
     "url": "https://data.asc-csa.gc.ca/en/dataset/e0333ed6-a614-46b1-b595-1fac1ce9214a",
     "how_it_helps": "Learn to open and visualize radar images with Python — a next step beyond the time series in this app."},
]

# Bump when VARIABLES / GIOVANNI_VARIABLES / DEMOS / RESOURCES change: catalog.xlsx is rebuilt automatically.
SEED_VERSION = "5"
# What is stored in catalog.xlsx: the seed version plus the sheet layout, so a new column
# in xlsx_store.py also forces a rebuild (even if SEED_VERSION was bumped first).
CATALOG_VERSION = f"{SEED_VERSION}+{CATALOG_SCHEMA}"


def _demo_request(variable_id: str, region: dict, start: int = 1981, end: int | None = None) -> dict:
    # end_year None -> the frontend fills in the last complete year
    return {
        "variable_id": variable_id,
        "region": region,
        "start_year": start,
        "end_year": end,
        "resolution": "monthly",
        "deseasonalize": True,
        "alpha": 0.05,
    }


DEMOS: list[dict] = [
    {
        "demo_id": "alaska-warming",
        "title": "Is Interior Alaska warming?",
        "story": "The Arctic is often said to be warming faster than the rest of the planet. Let's test that claim for the region around Fairbanks.",
        "request": _demo_request(
            "T2M",
            {"type": "bbox", "south": 63.5, "west": -150.0, "north": 66.5, "east": -146.0, "name": "Interior Alaska"},
        ),
        "compare_request": None,
        "narration_steps": [
            "Step 1 — WHAT: we pick 'Air temperature (2 m)'.",
            "Step 2 — WHERE: we draw a box around Interior Alaska, near Fairbanks.",
            "Step 3 — WHEN: we use every year from 1981 to the last complete year.",
            "The grey line is the raw data: big up-and-down swings are just summer and winter.",
            "Switch on 'Remove seasons' to see anomalies — how much warmer or colder each month was than usual.",
            "The orange line is the trend. The shaded band shows where the true trend probably lies (95 % confidence).",
            "Check the cards: the rate per decade, the total change, and whether both significance tests agree.",
        ],
    },
    {
        "demo_id": "sahel-rainfall",
        "title": "Is the Sahel getting wetter?",
        "story": "The Sahel, south of the Sahara, suffered severe droughts in the 1970s–80s. Has rainfall changed since 1981?",
        "request": _demo_request(
            "PRECTOTCORR",
            {"type": "bbox", "south": 12.0, "west": -2.0, "north": 16.0, "east": 2.0, "name": "Central Sahel"},
        ),
        "compare_request": None,
        "narration_steps": [
            "Step 1 — WHAT: we pick 'Precipitation'.",
            "Step 2 — WHERE: a box over the central Sahel (Burkina Faso, Mali, Niger).",
            "Step 3 — WHEN: 1981 to the last complete year.",
            "Rain here falls almost entirely in a short summer monsoon — that is why the raw data spikes once a year.",
            "Removing the seasonal cycle lets us compare every month fairly against its own normal.",
            "Rainfall is noisy. Look at the p-values: is the change bigger than what random wet and dry years could produce?",
        ],
    },
    {
        "demo_id": "opposite-trends",
        "title": "Same variable, opposite directions?",
        "story": "One process can push a variable up in one place and down in another. Compare rainfall trends in the Sahel and the U.S. Southwest.",
        "request": _demo_request(
            "PRECTOTCORR",
            {"type": "bbox", "south": 12.0, "west": -2.0, "north": 16.0, "east": 2.0, "name": "Central Sahel"},
        ),
        "compare_request": _demo_request(
            "PRECTOTCORR",
            {"type": "bbox", "south": 32.0, "west": -114.0, "north": 36.0, "east": -110.0, "name": "Arizona (U.S. Southwest)"},
        ),
        "narration_steps": [
            "We analyse the same variable — precipitation — for two regions over the same years.",
            "Region A: the central Sahel in Africa. Region B: Arizona in the U.S. Southwest.",
            "Both anomaly series are drawn on one chart so you can compare their trend lines.",
            "Read both verdict cards: do the trends point the same way? Are both significant?",
            "Key idea: a global change (like warming) can shift rain belts, making some regions wetter and others drier.",
        ],
    },
]


def ensure_catalog(data_dir: Path) -> bool:
    """Create catalog.xlsx, or rebuild it when SEED_VERSION or the sheet layout changed. Returns True if (re)written."""
    if (data_dir / CATALOG_FILE).exists() and read_catalog_version(data_dir) == CATALOG_VERSION:
        return False
    write_catalog(data_dir, ALL_VARIABLES, DEMOS, RESOURCES, CATALOG_VERSION)
    return True
