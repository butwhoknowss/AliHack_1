"""Turn a reverse-geocoded place into an honest label for a clicked point or drawn box.

WeatherAPI's search (q="lat,lon") returns the *nearest* named place, which can be hundreds of
km away over the ocean. So the label says how close it is:
  point: <= 50 km "El Chorro, Peru" · <= 150 km "near El Chorro, Peru" · farther "≈470 km from El Panteon, Peru"
  box:   <= 150 km "area around Arequipa, Peru" · farther "≈470 km from El Panteon, Peru"
50 km is about one NASA POWER grid cell, so a place that close is effectively "here".
"""

from __future__ import annotations

import math
from typing import Literal

MAX_NAME = 120  # Region.name max_length
SAME_PLACE_KM = 50.0
NEAR_KM = 150.0
SHORT_COUNTRY = {
    "United States of America": "USA",
    "United Kingdom of Great Britain and Northern Ireland": "UK",
}


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance (haversine)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(min(1.0, math.sqrt(a)))


def base_name(place: dict) -> str:
    name = str(place.get("name", "")).strip()
    country = str(place.get("country", "")).strip()
    region = str(place.get("region", "")).strip()
    short = SHORT_COUNTRY.get(country, country)
    parts = [name]
    if short == "USA" and region and region != name:
        parts.append(region)  # "Fairbanks, Alaska, USA" reads better than "Fairbanks, USA"
    if short and short != name:
        parts.append(short)
    return ", ".join(p for p in parts if p)


def place_label(place: dict, lat: float, lon: float, kind: Literal["point", "bbox"] = "point") -> tuple[str, float]:
    """(label, distance in km) for the region centred at lat/lon."""
    d = distance_km(lat, lon, float(place["lat"]), float(place["lon"]))
    base = base_name(place)
    if kind == "bbox":
        label = f"area around {base}" if d <= NEAR_KM else f"≈{round(d, -1):.0f} km from {base}"
    elif d <= SAME_PLACE_KM:
        label = base
    elif d <= NEAR_KM:
        label = f"near {base}"
    else:
        label = f"≈{round(d, -1):.0f} km from {base}"
    return label[:MAX_NAME], d
