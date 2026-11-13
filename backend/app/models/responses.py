"""Response schemas."""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, field_validator

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
    provider: Literal["power", "giovanni"] = "power"
    first_year: int = 1981
    available: bool = True          # False when the provider needs credentials that are missing
    unavailable_reason: str | None = None


class ResourceLink(BaseModel):
    key: str            # key of the related resource
    why: str            # how the two resources belong together


class Resource(BaseModel):
    key: str = ""
    step: str = ""      # data | test | check | explain (detective workflow)
    topics: str = ""    # comma-separated: atmosphere, water, air, land, statistics, canada
    title: str
    provider: str
    kind: str
    url: str
    how_it_helps: str
    used_in_app: bool
    related: list[ResourceLink] = []

    @field_validator("related", mode="before")
    @classmethod
    def _pairs_to_links(cls, v):
        """The catalog stores links compactly as [key, why] pairs."""
        return [{"key": x[0], "why": x[1]} if isinstance(x, (list, tuple)) else x for x in (v or [])]


class ResourceStep(BaseModel):
    step: str
    title: str
    intro: str


class NextStep(BaseModel):
    """A resource suggested after an analysis, with a reason tailored to that analysis."""
    key: str
    title: str
    url: str
    step: str
    why: str


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
    next_steps: list[NextStep] = []


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
    giovanni_configured: bool = False
    giovanni: bool | None = None     # None = credentials present but not checked yet
    giovanni_error: str | None = None  # why the Giovanni login check failed (no secrets)
