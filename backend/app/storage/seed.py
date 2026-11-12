"""Default content for data/catalog.xlsx (created on startup if missing).

To change the catalog: edit this file, delete data/catalog.xlsx, restart the API
(or edit catalog.xlsx directly in Excel while the server is stopped).
"""

from pathlib import Path

from .xlsx_store import CATALOG_FILE, write_catalog

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
    """Create catalog.xlsx from the defaults above if it does not exist. Returns True if created."""
    if (data_dir / CATALOG_FILE).exists():
        return False
    write_catalog(data_dir, VARIABLES, DEMOS)
    return True
