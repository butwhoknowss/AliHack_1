"""Suggest the challenge resources that fit one analysis ("next steps for this case").

Uses the relationships stored with each resource (step, topics, related) plus what the
analysis found: which variable, where, and whether the trend was significant.
"""

from __future__ import annotations

from ..models import AnalyzeResponse, NextStep, Region

MAX_SUGGESTIONS = 4

# Variables that weather stations also measure -> station records are a fair cross-check.
STATION_VARIABLES = {"T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR", "GPM_PRECIP", "AIRS_TSURF", "RH2M", "WS2M", "PS"}
LAND_VARIABLES = {"GWETTOP", "GWETROOT", "GLDAS_EVAP"}
WATER_VARIABLES = {"GLDAS_RUNOFF", "GLDAS_EVAP", "PRECTOTCORR", "GPM_PRECIP"}
# A POWER variable and the satellite variable that measures something similar.
SATELLITE_TWIN = {"PRECTOTCORR": "GPM_PRECIP", "T2M": "AIRS_TSURF"}


def region_center(region: Region) -> tuple[float, float]:
    if region.type == "point":
        return float(region.lat), float(region.lon)
    return (region.south + region.north) / 2, (region.west + region.east) / 2


def in_or_near_canada(region: Region) -> bool:
    """Rough box test (no borders file): Canada spans ~41.7-83.5N, 141-52.6W; south of 49N only east of 95W."""
    lat, lon = region_center(region)
    if not (41.7 <= lat <= 83.5 and -141.0 <= lon <= -52.6):
        return False
    return lat >= 49.0 or lon > -95.0


def suggest_next_steps(resources: list[dict], res: AnalyzeResponse) -> list[NextStep]:
    by_key = {r.get("key"): r for r in resources if r.get("key")}
    var = res.variable
    name = var.name
    place = res.region.label()
    agreement = res.trend.agreement
    slope = res.trend.ols.slope_per_decade
    direction = "upward" if slope > 0 else "downward" if slope < 0 else "flat"
    years = res.period[1] - res.period[0] + 1

    picks: list[tuple[str, str]] = []

    # 1. Cross-check with an independent witness
    if var.id in STATION_VARIABLES:
        picks.append(("cdo", f"Check this {direction} trend against real weather-station records near {place}. "
                             "This app averages grid cells about 50 km wide, while a station measures one spot."))

    # 2. Understand the statistics behind the verdict
    if agreement == "neither":
        picks.append(("significance", f"'Not significant' after {years} years doesn't prove nothing is changing. "
                                      "This guide explains what a p-value can and cannot tell you."))
    elif agreement in ("ols_only", "mk_only"):
        picks.append(("trendtests", "The two tests disagree here. This article explains how the t-test and "
                                    "Mann-Kendall test differ, and when each one is more reliable."))
    else:
        picks.append(("trendtests", "Both tests agree. See how the t-test and Mann-Kendall test work, "
                                    "and why this app corrects for autocorrelation."))

    # 3. The data source behind this variable, and related data tools
    if var.provider == "giovanni":
        picks.append(("giovanni", f"Open Giovanni to see a map of {name}. You can check whether the whole region "
                                  "changes, not just the sample points used here."))
    if var.id in LAND_VARIABLES:
        picks.append(("appeears", f"Zoom in: get fine-resolution land data, such as vegetation greenness, for {place}. "
                                  "Then see whether the plants respond to this change."))
    if var.id == "GLDAS_RUNOFF":
        picks.append(("swot", "SWOT measures river and lake heights directly from space. Its record began in 2022, "
                              "so it's too short for a trend test today, but it will be able to confirm runoff trends."))
    elif var.id in WATER_VARIABLES and var.provider == "giovanni":
        picks.append(("hydrology", "This GLDAS/GPM water data used to come from NASA's Hydrology Time Series tool, "
                                   "which is now retired. Giovanni has replaced it."))

    # 4. Canadian regions: Canadian data and missions
    if in_or_near_canada(res.region):
        picks.append(("geo", f"{place} is in or near Canada. Geo.ca has Canada's open maps and data for this area."))
        picks.append(("rcm", "Canada's RADARSAT satellites watch this area day or night and through cloud. "
                             "They track wetlands, floods and crops, and sea ice along the coasts."))

    # 5. Broader cross-check and a worked example of the same method
    picks.append(("knmi", f"Double-check the {direction} trend with other datasets and methods in the KNMI Climate Explorer."))
    if res.deseasonalize:
        picks.append(("seawifs", "A NASA study that followed the same recipe: build a monthly series, "
                                 "remove the seasons, then test the trend."))

    out: list[NextStep] = []
    seen: set[str] = set()
    for key, why in picks:
        r = by_key.get(key)
        if r is None or key in seen:
            continue
        seen.add(key)
        out.append(NextStep(key=key, title=r["title"], url=r["url"], step=r.get("step", ""), why=why))
        if len(out) >= MAX_SUGGESTIONS:
            break
    return out
