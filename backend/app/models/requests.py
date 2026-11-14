"""Request schemas."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

MAX_BOX_DEGREES = 5.0
MIN_YEARS = 10
FIRST_YEAR = 1981


def last_complete_year() -> int:
    return date.today().year - 1


def _fmt_coord(v: float, nd: int, pos: str, neg: str) -> str:
    """Hemisphere letter instead of a minus sign: -19.5 -> '19.5°S'. Zero (after rounding) has no letter."""
    r = round(float(v), nd)
    if r == 0:
        return f"{0:.{nd}f}°"
    return f"{abs(r):.{nd}f}°{pos if r > 0 else neg}"


def fmt_lat(v: float, nd: int = 1) -> str:
    return _fmt_coord(v, nd, "N", "S")


def fmt_lon(v: float, nd: int = 1) -> str:
    if abs(round(float(v), nd)) == 180:
        return f"{180:.{nd}f}°"  # the antimeridian is neither east nor west
    return _fmt_coord(v, nd, "E", "W")


def fmt_range(a: float, b: float, fmt) -> str:
    """'19.5°S–14.5°S' (en dash, no minus signs)."""
    return f"{fmt(a)}–{fmt(b)}"


class Region(BaseModel):
    type: Literal["point", "bbox"]
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)
    south: float | None = Field(None, ge=-90, le=90)
    west: float | None = Field(None, ge=-180, le=180)
    north: float | None = Field(None, ge=-90, le=90)
    east: float | None = Field(None, ge=-180, le=180)
    name: str | None = Field(None, max_length=120)

    @model_validator(mode="after")
    def _check_shape(self) -> "Region":
        if self.type == "point":
            if self.lat is None or self.lon is None:
                raise ValueError("A point region needs both lat and lon.")
        else:
            vals = (self.south, self.west, self.north, self.east)
            if any(v is None for v in vals):
                raise ValueError("A box region needs south, west, north and east.")
            if not self.south < self.north:
                raise ValueError("south must be less than north.")
            if not self.west < self.east:
                raise ValueError("west must be less than east (boxes crossing the dateline are not supported).")
            if self.north - self.south > MAX_BOX_DEGREES or self.east - self.west > MAX_BOX_DEGREES:
                raise ValueError(f"Box is too large: each side must be at most {MAX_BOX_DEGREES:g} degrees.")
        return self

    def label(self) -> str:
        if self.name:
            return self.name
        if self.type == "point":
            return f"{fmt_lat(self.lat, 2)}, {fmt_lon(self.lon, 2)}"
        return f"box {fmt_range(self.south, self.north, fmt_lat)}, {fmt_range(self.west, self.east, fmt_lon)}"


class AnalyzeRequest(BaseModel):
    variable_id: str = Field(..., min_length=1, max_length=40)
    region: Region
    start_year: int = Field(..., ge=FIRST_YEAR)
    end_year: int
    resolution: Literal["monthly", "daily"] = "monthly"
    deseasonalize: bool = True
    alpha: float = Field(0.05, gt=0, lt=0.5)
    save: bool = True
    # Unit to show results in (an id from Variable.unit_options); None = the variable's own unit.
    units: str | None = Field(None, max_length=20)

    @model_validator(mode="after")
    def _check_period(self) -> "AnalyzeRequest":
        last = last_complete_year()
        if self.end_year > last:
            raise ValueError(f"end_year must be {last} or earlier (the last complete year of data).")
        if self.end_year - self.start_year + 1 < MIN_YEARS:
            raise ValueError(f"Choose at least {MIN_YEARS} years so a trend can be tested.")
        return self
