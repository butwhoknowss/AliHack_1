from typing import Literal

from fastapi import APIRouter, Depends, Query

from ..deps import get_weather
from ..errors import NotFoundError
from ..models import Location, ReverseLocation
from ..services.places import place_label
from ..sources.weatherapi import WeatherApiSource

router = APIRouter(tags=["locations"])


@router.get("/locations/search", response_model=list[Location])
async def search_locations(
    q: str = Query(..., min_length=2, max_length=100),
    weather: WeatherApiSource = Depends(get_weather),
) -> list[Location]:
    results = await weather.search(q.strip())
    if not results:
        raise NotFoundError(f"No place found for '{q}'.")
    return [Location(**r) for r in results]


@router.get("/locations/reverse", response_model=ReverseLocation)
async def reverse_location(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    kind: Literal["point", "bbox"] = "point",
    weather: WeatherApiSource = Depends(get_weather),
) -> ReverseLocation:
    """Name for a clicked point (or the centre of a drawn box), honest about distance."""
    place = await weather.reverse(lat, lon)
    if place is None:
        raise NotFoundError("No named place found near this location.")
    label, dist = place_label(place, lat, lon, kind)
    return ReverseLocation(**place, distance_km=round(dist, 1), label=label)
