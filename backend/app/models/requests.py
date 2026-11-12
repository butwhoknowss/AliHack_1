"""Request schemas."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

MAX_BOX_DEGREES = 5.0
MIN_YEARS = 10
FIRST_YEAR = 1981


def last_complete_year() -> int:
    return date.today().year - 1


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
            return f"{self.lat:.2f}, {self.lon:.2f}"
        return f"box {self.south:.1f}..{self.north:.1f}N, {self.west:.1f}..{self.east:.1f}E"


class AnalyzeRequest(BaseModel):
    variable_id: str = Field(..., min_length=1, max_length=40)
    region: Region
    start_year: int = Field(..., ge=FIRST_YEAR)
    end_year: int
    resolution: Literal["monthly", "daily"] = "monthly"
    deseasonalize: bool = True
    alpha: float = Field(0.05, gt=0, lt=0.5)
    save: bool = True

    @model_validator(mode="after")
    def _check_period(self) -> "AnalyzeRequest":
        last = last_complete_year()
        if self.end_year > last:
            raise ValueError(f"end_year must be {last} or earlier (the last complete year of data).")
        if self.end_year - self.start_year + 1 < MIN_YEARS:
            raise ValueError(f"Choose at least {MIN_YEARS} years so a trend can be tested.")
        return self
