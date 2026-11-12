"""Orchestrates one analysis: fetch -> clean -> stats -> explain -> (save)."""

from __future__ import annotations

import json
import math
import uuid
from datetime import UTC, datetime

import pandas as pd

from ..errors import DataQualityError, NotFoundError
from ..models import (
    AnalyzeRequest,
    AnalyzeResponse,
    CIPoint,
    MannKendallResult,
    OLSResult,
    SeriesPoint,
    TrendResult,
    Variable,
)
from ..sources.nasa_power import NasaPowerSource
from ..storage.xlsx_store import XlsxStore
from .explain import build_hints, build_verdict
from .series import regional_series, to_monthly
from .trend import analyze_series

MAX_MISSING_FRACTION = 0.2
# Temperatures in °C are not ratio-scale, so "percent change" would be meaningless.
NON_RATIO_VARIABLES = {"T2M", "T2M_MAX", "T2M_MIN"}


def _clean(x: float | None, nd: int = 4) -> float | None:
    if x is None:
        return None
    x = float(x)
    return None if math.isnan(x) or math.isinf(x) else round(x, nd)


def get_variable(variables: dict[str, dict], variable_id: str) -> Variable:
    row = variables.get(variable_id)
    if row is None:
        raise NotFoundError(f"Unknown variable '{variable_id}'.")
    return Variable(**row)


async def run_analysis(
    req: AnalyzeRequest,
    *,
    variables: dict[str, dict],
    source: NasaPowerSource,
    store: XlsxStore,
    analysis_id: str | None = None,
) -> AnalyzeResponse:
    variable = get_variable(variables, req.variable_id)

    series, n_points = await regional_series(
        source, store, req.variable_id, req.region, req.start_year, req.end_year, req.resolution
    )
    monthly = to_monthly(series) if req.resolution == "daily" else series
    monthly = monthly.reindex(pd.date_range(f"{req.start_year}-01-01", f"{req.end_year}-12-01", freq="MS"))

    missing_fraction = float(monthly.isna().mean())
    if missing_fraction > MAX_MISSING_FRACTION:
        raise DataQualityError(
            f"{missing_fraction:.0%} of the months have no data for this region and variable "
            "(for example soil moisture over the ocean). Try another place or variable."
        )

    try:
        comp = analyze_series(
            monthly,
            req.start_year,
            req.end_year,
            deseasonalize=req.deseasonalize,
            alpha=req.alpha,
            ratio_scale=req.variable_id not in NON_RATIO_VARIABLES,
        )
    except ValueError as exc:
        raise DataQualityError(str(exc)) from exc

    label = req.region.label()
    verdict = build_verdict(
        variable.name, variable.units, label, req.start_year, req.end_year,
        comp.ols, comp.mann_kendall, comp.total_change, comp.agreement, req.alpha,
    )
    hints = build_hints(
        req.start_year, req.end_year, req.deseasonalize, variable.seasonal,
        missing_fraction, comp.ols, comp.agreement, req.resolution,
    )

    anomalies = comp.anomalies
    points = [
        SeriesPoint(
            date=ts.date(),
            value=_clean(val),
            anomaly=_clean(anomalies.loc[ts]) if anomalies is not None else None,
        )
        for ts, val in monthly.items()
    ]
    trend_line = [SeriesPoint(date=ts.date(), value=_clean(v)) for ts, v in comp.fitted.items()]
    ci_band = [
        CIPoint(date=ts.date(), low=round(float(lo), 4), high=round(float(hi), 4))
        for (ts, lo), hi in zip(comp.ci_low.items(), comp.ci_high.to_numpy(), strict=True)
    ]

    trend = TrendResult(
        ols=OLSResult(**{k: (v if k == "n" else round(float(v), 6)) for k, v in comp.ols.items()}),
        mann_kendall=MannKendallResult(
            **{k: (v if k in ("test", "trend") else round(float(v), 6)) for k, v in comp.mann_kendall.items()}
        ),
        total_change=round(comp.total_change, 6),
        percent_change=_clean(comp.percent_change, 3),
        significant=comp.significant,
        agreement=comp.agreement,
        verdict=verdict,
        hints=hints,
    )

    response = AnalyzeResponse(
        analysis_id=analysis_id or uuid.uuid4().hex,
        variable=variable,
        region=req.region,
        resolution=req.resolution,
        deseasonalize=req.deseasonalize,
        alpha=req.alpha,
        period=(req.start_year, req.end_year),
        series=points,
        trend_line=trend_line,
        ci_band=ci_band,
        trend=trend,
        missing_fraction=round(missing_fraction, 4),
        n_sample_points=n_points,
        source_citation=source.citation,
        created_at=datetime.now(UTC),
    )

    if req.save and analysis_id is None:
        row = {
            "analysis_id": response.analysis_id,
            "created_at": response.created_at.isoformat(),
            "variable_id": req.variable_id,
            "region_json": req.region.model_dump_json(),
            "start_year": req.start_year,
            "end_year": req.end_year,
            "resolution": req.resolution,
            "deseasonalize": req.deseasonalize,
            "alpha": req.alpha,
            "ols_slope_per_decade": trend.ols.slope_per_decade,
            "ols_p": trend.ols.p_value,
            "mk_p": trend.mann_kendall.p_value,
            "sens_slope_per_decade": trend.mann_kendall.sens_slope_per_decade,
            "significant": trend.significant,
            "verdict": verdict,
            "request_json": json.dumps(req.model_dump(mode="json")),
        }
        series_df = pd.DataFrame(
            {
                "analysis_id": response.analysis_id,
                "date": [p.date for p in points],
                "value": [p.value for p in points],
                "anomaly": [p.anomaly for p in points],
            }
        )
        await store.asave_analysis(row, series_df)

    return response
