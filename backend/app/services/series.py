"""Fetch (with cache) and combine a regional time series."""

from __future__ import annotations

import asyncio
import hashlib

import numpy as np
import pandas as pd

from ..models.requests import Region
from ..sources.giovanni import GiovanniSource
from ..sources.nasa_power import NasaPowerSource
from ..storage.xlsx_store import XlsxStore
from .region import sample_points


def cache_key(source: str, variable_id: str, lat: float, lon: float, resolution: str, start: int, end: int) -> str:
    raw = f"{source}|{variable_id}|{lat:.3f},{lon:.3f}|{resolution}|{start}|{end}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def full_index(start_year: int, end_year: int, resolution: str) -> pd.DatetimeIndex:
    if resolution == "monthly":
        return pd.date_range(f"{start_year}-01-01", f"{end_year}-12-01", freq="MS")
    return pd.date_range(f"{start_year}-01-01", f"{end_year}-12-31", freq="D")


def weighted_mean(series_list: list[pd.Series], weights: list[float], index: pd.DatetimeIndex) -> pd.Series:
    """Weighted mean per timestamp; NaNs are skipped and remaining weights renormalised."""
    frame = pd.concat([s.reindex(index) for s in series_list], axis=1)
    values = frame.to_numpy(dtype=float)
    w = np.asarray(weights, dtype=float)[None, :]
    mask = ~np.isnan(values)
    wsum = (w * mask).sum(axis=1)
    num = np.nansum(values * w, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(wsum > 0, num / wsum, np.nan)
    return pd.Series(out, index=index)


def max_points_per_side(provider: str, resolution: str) -> int:
    """Giovanni is point-only and slow -> 3x3; POWER daily payloads are large -> 2x2."""
    if provider == "giovanni":
        return 3
    return 5 if resolution == "monthly" else 2


async def regional_series(
    sources: dict[str, NasaPowerSource | GiovanniSource],
    store: XlsxStore,
    variable: dict,
    region: Region,
    start_year: int,
    end_year: int,
    resolution: str,
) -> tuple[pd.Series, int]:
    """Return (regional series on a complete date index, number of sample points)."""
    provider = variable.get("provider", "power")
    source = sources[provider]
    variable_id = variable["id"]
    points = sample_points(region, max_side=max_points_per_side(provider, resolution))
    keys = [cache_key(source.name, variable_id, la, lo, resolution, start_year, end_year) for la, lo, _ in points]

    cached = await asyncio.gather(*(store.aget_cached(k, resolution) for k in keys))
    missing = [i for i, s in enumerate(cached) if s is None]

    def fetch(i: int):
        lat, lon = points[i][0], points[i][1]
        if provider == "giovanni":
            return source.fetch_point(
                variable_id, lat, lon, start_year, end_year, resolution,
                provider_id=variable["provider_id"], scale=variable["scale"], offset=variable["offset"],
            )
        return source.fetch_point(variable_id, lat, lon, start_year, end_year, resolution)

    fetched = await asyncio.gather(*(fetch(i) for i in missing))
    results: list[pd.Series] = list(cached)
    new_entries = []
    for i, s in zip(missing, fetched, strict=True):
        results[i] = s
        new_entries.append(
            (
                {
                    "cache_key": keys[i],
                    "source": source.name,
                    "variable_id": variable_id,
                    "lat": points[i][0],
                    "lon": points[i][1],
                    "resolution": resolution,
                    "start_year": start_year,
                    "end_year": end_year,
                },
                s,
            )
        )
    if new_entries:
        await store.aput_cached_many(new_entries)

    index = full_index(start_year, end_year, resolution)
    combined = weighted_mean(results, [w for _, _, w in points], index)
    return combined, len(points)


def to_monthly(series: pd.Series) -> pd.Series:
    """Aggregate a daily series to monthly means (month needs >= 50 % valid days)."""
    grouped = series.groupby(series.index.to_period("M"))
    means = grouped.mean()
    valid = grouped.count() / grouped.size()
    means[valid < 0.5] = np.nan
    means.index = means.index.to_timestamp(how="start")
    return means
