from fastapi import APIRouter, Depends, Query

from ..deps import get_weather
from ..errors import NotFoundError
from ..models import Location
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
