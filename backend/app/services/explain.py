"""Plain-language verdicts and hints for students and the public."""

from __future__ import annotations


def fmt_num(x: float) -> str:
    ax = abs(x)
    if ax == 0:
        return "0"
    if ax >= 100:
        return f"{x:,.0f}"
    if ax >= 10:
        return f"{x:.1f}"
    if ax >= 0.1:
        return f"{x:.2f}"
    if ax >= 0.001:
        return f"{x:.3f}"
    return f"{x:.2e}"


def fmt_p(p: float) -> str:
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def build_verdict(
    variable_name: str,
    units: str,
    region_label: str,
    start_year: int,
    end_year: int,
    ols: dict,
    mk_res: dict,
    total_change: float,
    agreement: str,
    alpha: float,
) -> str:
    slope = ols["slope_per_decade"]
    direction = "increased" if slope > 0 else "decreased" if slope < 0 else "stayed flat"
    rate = f"{fmt_num(abs(slope))} {units} per decade"
    total = f"{fmt_num(abs(total_change))} {units} over {start_year}–{end_year}"
    ptxt = f"t-test {fmt_p(ols['p_value'])}, Mann-Kendall {fmt_p(mk_res['p_value'])}"
    conf = f"{round((1 - alpha) * 100):g}%"

    head = f"{variable_name} in {region_label} {direction} by about {rate} ({total})."
    if agreement == "both":
        return (
            f"{head} Both tests agree this trend is statistically significant ({ptxt}): "
            f"it is very unlikely to be just random year-to-year variation (at the {conf} confidence level)."
        )
    if agreement in ("ols_only", "mk_only"):
        which = "the t-test" if agreement == "ols_only" else "the Mann-Kendall test"
        return (
            f"{head} The evidence is mixed: only {which} finds a significant trend ({ptxt}). "
            "Treat this as a possible trend that needs more data or a closer look."
        )
    return (
        f"{head} This is not statistically significant ({ptxt}): natural ups and downs could "
        "explain a change this size. That does not prove nothing is changing — it means we can't be sure yet."
    )


def build_hints(
    start_year: int,
    end_year: int,
    deseasonalize: bool,
    seasonal_variable: bool,
    missing_fraction: float,
    ols: dict,
    agreement: str,
    resolution: str,
) -> list[str]:
    hints: list[str] = []
    years = end_year - start_year + 1
    if years < 20:
        hints.append(f"You used {years} years. Trends often only become significant with 20–30+ years — try a longer period.")
    if agreement != "both" and years < 30:
        hints.append("Not significant yet? A longer record reduces the effect of random wet/dry or warm/cold years.")
    if seasonal_variable and not deseasonalize:
        hints.append("This variable has a strong seasonal cycle. Turn on 'Remove seasons' for a fairer trend test.")
    if missing_fraction > 0.10:
        hints.append(f"{missing_fraction:.0%} of the data are missing, which weakens the tests.")
    if ols["n_effective"] < ols["n"] * 0.3:
        hints.append(
            "Neighbouring months are strongly similar (autocorrelation), so the data contain less independent "
            "information than their count suggests. The t-test was adjusted for this."
        )
    if ols["r_squared"] < 0.05 and agreement == "both":
        hints.append("The trend is significant but small compared with the month-to-month variability.")
    if resolution == "daily":
        hints.append("Daily data were averaged into monthly values before testing, because day-to-day weather is highly autocorrelated.")
    hints.append("Try the same variable in another region: trends can go the opposite way elsewhere, even when the same process drives both.")
    return hints
