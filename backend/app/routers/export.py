import io
from typing import Literal

import pandas as pd
from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import Response

from ..deps import get_sources, get_store, get_variables
from ..storage.xlsx_store import XlsxStore
from .analyze import ID_PATTERN, reload_analysis

router = APIRouter(tags=["export"])

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/export/{analysis_id}")
async def export_analysis(
    analysis_id: str = Path(..., pattern=ID_PATTERN),
    format: Literal["xlsx", "csv"] = Query("xlsx"),
    variables: dict[str, dict] = Depends(get_variables),
    sources: dict = Depends(get_sources),
    store: XlsxStore = Depends(get_store),
) -> Response:
    res = await reload_analysis(analysis_id, variables, sources, store)
    units = res.variable.units
    trend_by_date = {p.date: p.value for p in res.trend_line}
    data = pd.DataFrame(
        {
            "date": [p.date for p in res.series],
            f"value ({units})": [p.value for p in res.series],
            f"anomaly ({units})": [p.anomaly for p in res.series],
            f"trend line ({units})": [trend_by_date.get(p.date) for p in res.series],
        }
    )
    ols, mk = res.trend.ols, res.trend.mann_kendall
    summary = pd.DataFrame(
        [
            ("Variable", f"{res.variable.name} ({res.variable.id})"),
            ("Units", units),
            ("Region", res.region.label()),
            ("Period", f"{res.period[0]}-{res.period[1]}"),
            ("Seasonal cycle removed", res.deseasonalize),
            ("Significance level (alpha)", res.alpha),
            ("OLS slope per decade", ols.slope_per_decade),
            ("OLS 95% CI low per decade", ols.ci95_low_per_decade),
            ("OLS 95% CI high per decade", ols.ci95_high_per_decade),
            ("OLS t-test p-value", ols.p_value),
            ("OLS R squared", ols.r_squared),
            ("Effective sample size", ols.n_effective),
            ("Mann-Kendall test", mk.test),
            ("Mann-Kendall p-value", mk.p_value),
            ("Sen's slope per decade", mk.sens_slope_per_decade),
            ("Total change", res.trend.total_change),
            ("Percent change", res.trend.percent_change),
            ("Significant (both tests)", res.trend.significant),
            ("Verdict", res.trend.verdict),
            ("Source", res.source_citation),
        ],
        columns=["item", "value"],
    )
    filename = f"trend_{res.variable.id}_{analysis_id[:8]}"

    if format == "csv":
        body = data.to_csv(index=False)
        return Response(
            content=body.encode("utf-8-sig"),  # BOM so Excel shows °C correctly
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
        )

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="summary", index=False)
        data.to_excel(writer, sheet_name="series", index=False)
    return Response(
        content=buf.getvalue(),
        media_type=XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'},
    )
