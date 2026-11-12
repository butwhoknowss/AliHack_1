import asyncio
import time

from fastapi import APIRouter, Depends, Request

from ..deps import get_power, get_store, get_weather
from ..models import Health
from ..sources.nasa_power import NasaPowerSource
from ..sources.weatherapi import WeatherApiSource
from ..storage.xlsx_store import XlsxStore

router = APIRouter(tags=["health"])

_CHECK_TTL_SECONDS = 300


@router.get("/health", response_model=Health)
async def health(
    request: Request,
    power: NasaPowerSource = Depends(get_power),
    weather: WeatherApiSource = Depends(get_weather),
    store: XlsxStore = Depends(get_store),
) -> Health:
    """Liveness plus (cached for 5 minutes) upstream reachability."""
    state = request.app.state
    cached = getattr(state, "health_cache", None)
    now = time.monotonic()
    if cached is None or now - cached[0] > _CHECK_TTL_SECONDS:
        power_ok, weather_ok = await asyncio.gather(power.ping(), weather.ping())
        state.health_cache = (now, power_ok, weather_ok)
    _, power_ok, weather_ok = state.health_cache
    storage_ok = await asyncio.to_thread(store.storage_ok)
    return Health(
        status="ok",
        nasa_power=power_ok,
        weatherapi=weather_ok,
        storage=storage_ok,
        weatherapi_configured=weather.configured,
    )
