"""Accessors for objects created in the app lifespan (stored on app.state)."""

from fastapi import Request

from .sources.nasa_power import NasaPowerSource
from .sources.weatherapi import WeatherApiSource
from .storage.xlsx_store import XlsxStore


def get_store(request: Request) -> XlsxStore:
    return request.app.state.store


def get_power(request: Request) -> NasaPowerSource:
    return request.app.state.power


def get_weather(request: Request) -> WeatherApiSource:
    return request.app.state.weather


def get_variables(request: Request) -> dict[str, dict]:
    return request.app.state.variables


def get_demos(request: Request) -> list[dict]:
    return request.app.state.demos
