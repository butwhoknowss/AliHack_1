"""Response schemas."""

import datetime as dt
from typing import Literal

from pydantic import BaseModel

from .requests import Region


class Variable(BaseModel):
    id: str
    name: str
    category: str
    units: str
    definition: str
    why_it_matters: str
    example_question: str
    source: str
    seasonal: bool


class SeriesPoint(BaseModel):
    date: dt.date
    value: float | None
    anomaly: float | None = None


class CIPoint(BaseModel):
    date: dt.date
    low: float
    high: float


class OLSResult(BaseModel):
    slope_per_year: float
    slope_per_decade: float
    intercept: float
    ci95_low_per_decade: float
    ci95_high_per_decade: float
    t_stat: float
    p_value: float
    r_squared: float
    n: int
    n_effective: float


class MannKendallResult(BaseModel):
    test: Literal["original", "hamed_rao", "seasonal"]
    trend: Literal["increasing", "decreasing", "no trend"]
    p_value: float
    z: float
    tau: float
    s: float
    sens_slope_per_decade: float


class TrendResult(BaseModel):
    ols: OLSResult
    mann_kendall: MannKendallResult
    total_change: float
    percent_change: float | None
    significant: bool
    agreement: Literal["both", "ols_only", "mk_only", "neither"]
    verdict: str
    hints: list[str]


class AnalyzeResponse(BaseModel):
    analysis_id: str
    variable: Variable
    region: Region
    resolution: str
    deseasonalize: bool
    alpha: float
    period: tuple[int, int]
    series: list[SeriesPoint]
    trend_line: list[SeriesPoint]
    ci_band: list[CIPoint]
    trend: TrendResult
    missing_fraction: float
    n_sample_points: int
    source_citation: str
    created_at: dt.datetime


class TimeseriesResponse(BaseModel):
    variable: Variable
    region: Region
    resolution: str
    series: list[SeriesPoint]
    missing_fraction: float
    n_sample_points: int
    source_citation: str


class Location(BaseModel):
    name: str
    region: str
    country: str
    lat: float
    lon: float


class CurrentWeather(BaseModel):
    location: str
    country: str
    local_time: str
    temp_c: float
    feelslike_c: float
    humidity: int
    wind_kph: float
    precip_mm: float
    condition: str
    icon: str


class Demo(BaseModel):
    demo_id: str
    title: str
    story: str
    request: dict
    compare_request: dict | None = None
    narration_steps: list[str]


class Health(BaseModel):
    status: str
    nasa_power: bool
    weatherapi: bool
    storage: bool
    weatherapi_configured: bool
