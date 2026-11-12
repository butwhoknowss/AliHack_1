"""Turn a Region into sample points + area weights."""

from __future__ import annotations

import math

from ..models.requests import Region

MAX_POINTS_PER_SIDE = 5   # 5 x 5 = 25 points max
TARGET_STEP_DEG = 1.0     # ~ MERRA-2 grid is 0.5 x 0.625 deg, so 1 deg avoids duplicate cells


def _axis(lo: float, hi: float, max_side: int) -> list[float]:
    span = hi - lo
    n = max(1, min(max_side, round(span / TARGET_STEP_DEG)))
    step = span / n
    # cell centres: evenly spaced, never on the box edge
    return [round(lo + step * (i + 0.5), 4) for i in range(n)]


def sample_points(region: Region, max_side: int = MAX_POINTS_PER_SIDE) -> list[tuple[float, float, float]]:
    """Return [(lat, lon, weight)], weights = cos(latitude), normalised to sum to 1.

    ``max_side`` caps points per side (daily requests use fewer points: they are much larger).
    """
    if region.type == "point":
        return [(float(region.lat), float(region.lon), 1.0)]
    lats = _axis(region.south, region.north, max_side)
    lons = _axis(region.west, region.east, max_side)
    pts = [(la, lo, max(math.cos(math.radians(la)), 1e-6)) for la in lats for lo in lons]
    total = sum(w for _, _, w in pts)
    return [(la, lo, w / total) for la, lo, w in pts]
