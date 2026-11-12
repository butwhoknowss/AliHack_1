from fastapi import APIRouter, Depends, Query

from ..deps import get_weather
from ..models import CurrentWeather
from ..sources.weatherapi import WeatherApiSource

router = APIRouter(tags=["weather"])


@router.get("/weather/current", response_model=CurrentWeather)
async def current_weather(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    weather: WeatherApiSource = Depends(get_weather),
) -> CurrentWeather:
    return CurrentWeather(**await weather.current(lat, lon))
