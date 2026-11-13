import math
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError

from ..deps import get_sources, get_store, get_variables
from ..models import Region, SeriesPoint, TimeseriesResponse
from ..models.requests import FIRST_YEAR, last_complete_year
from ..services.analysis import check_request_fits_variable, get_variable
from ..services.series import regional_series
from ..storage.xlsx_store import XlsxStore

router = APIRouter(tags=["timeseries"])

MAX_DAILY_YEARS = 10


@router.get("/timeseries", response_model=TimeseriesResponse)
async def timeseries(
    variable_id: str = Query(..., max_length=40),
    start_year: int = Query(..., ge=FIRST_YEAR),
    end_year: int = Query(...),
    resolution: Literal["monthly", "daily"] = "monthly",
    lat: float | None = Query(None, ge=-90, le=90),
    lon: float | None = Query(None, ge=-180, le=180),
    south: float | None = Query(None, ge=-90, le=90),
    west: float | None = Query(None, ge=-180, le=180),
    north: float | None = Query(None, ge=-90, le=90),
    east: float | None = Query(None, ge=-180, le=180),
    name: str | None = Query(None, max_length=120),
    variables: dict[str, dict] = Depends(get_variables),
    sources: dict = Depends(get_sources),
    store: XlsxStore = Depends(get_store),
) -> TimeseriesResponse:
    """Raw regional series (no statistics). Daily requests are limited to 10 years."""
    variable = get_variable(variables, variable_id, sources.get("giovanni"))
    check_request_fits_variable(variable, start_year, resolution)
    if end_year > last_complete_year() or end_year < start_year:
        raise HTTPException(422, f"end_year must be between start_year and {last_complete_year()}.")
    if resolution == "daily" and end_year - start_year + 1 > MAX_DAILY_YEARS:
        raise HTTPException(422, f"Daily series are limited to {MAX_DAILY_YEARS} years; use monthly for longer periods.")
    rtype = "point" if lat is not None and lon is not None else "bbox"
    try:
        region = Region(type=rtype, lat=lat, lon=lon, south=south, west=west, north=north, east=east, name=name)
    except ValidationError as exc:
        raise HTTPException(422, exc.errors()[0]["msg"]) from exc

    series, n_points = await regional_series(
        sources, store, variables[variable_id], region, start_year, end_year, resolution
    )
    points = [
        SeriesPoint(date=ts.date(), value=None if math.isnan(v) else round(float(v), 4))
        for ts, v in series.items()
    ]
    return TimeseriesResponse(
        variable=variable,
        region=region,
        resolution=resolution,
        series=points,
        missing_fraction=round(float(series.isna().mean()), 4),
        n_sample_points=n_points,
        source_citation=sources[variable.provider].citation,
    )
