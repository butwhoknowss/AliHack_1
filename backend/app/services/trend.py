"""Trend statistics for a monthly series (Architecture.md section 9).

All functions are pure (no IO) so they are easy to test with synthetic data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
import pymannkendall as mk
from scipy import stats

MIN_VALID_POINTS = 24


@dataclass
class TrendComputation:
    target: pd.Series            # series the tests ran on (anomalies or raw), full index
    anomalies: pd.Series | None  # anomalies (None if not deseasonalized)
    fitted: pd.Series            # OLS fitted line on the full index
    ci_low: pd.Series
    ci_high: pd.Series
    ols: dict
    mann_kendall: dict
    total_change: float
    percent_change: float | None
    significant: bool
    agreement: str


def decimal_year(index: pd.DatetimeIndex) -> np.ndarray:
    """Mid-month decimal year, e.g. Jan 2000 -> 2000.0417."""
    return index.year.to_numpy(dtype=float) + (index.month.to_numpy(dtype=float) - 0.5) / 12.0


def monthly_anomalies(series: pd.Series) -> pd.Series:
    """Subtract each calendar month's mean (the climatology) over the period."""
    clim = series.groupby(series.index.month).transform("mean")
    return series - clim


def _lag1_autocorr(resid: np.ndarray) -> float:
    if resid.size < 3:
        return 0.0
    a, b = resid[:-1], resid[1:]
    if np.std(a) == 0 or np.std(b) == 0:
        return 0.0
    r = float(np.corrcoef(a, b)[0, 1])
    return 0.0 if math.isnan(r) else r


def ols_trend(y: pd.Series, alpha: float = 0.05) -> tuple[dict, pd.Series, pd.Series, pd.Series]:
    """OLS slope with lag-1 autocorrelation-adjusted t-test and CI.

    Returns (result dict, fitted, ci_low, ci_high) — the last three on y's full index.
    """
    valid = y.dropna()
    n = int(valid.size)
    x = decimal_year(valid.index)
    v = valid.to_numpy(dtype=float)
    x_all = decimal_year(y.index)

    x_mean = float(x.mean())
    sxx = float(((x - x_mean) ** 2).sum())
    if sxx == 0:
        raise ValueError("Time values have no spread.")
    slope = float(((x - x_mean) * (v - v.mean())).sum() / sxx)
    icpt = float(v.mean() - slope * x_mean)
    resid = v - (icpt + slope * x)
    sse = float((resid**2).sum())
    sst = float(((v - v.mean()) ** 2).sum())
    r2 = 0.0 if sst == 0 else 1.0 - sse / sst
    sigma2 = sse / (n - 2)

    r1 = _lag1_autocorr(resid)
    n_eff = n * (1 - r1) / (1 + r1) if r1 > 0 else float(n)
    n_eff = max(min(n_eff, float(n)), 3.0)
    df = n_eff - 2.0
    inflate = math.sqrt((n - 2) / df)

    se_slope = math.sqrt(sigma2 / sxx) * inflate
    if se_slope == 0:
        t_stat, p_value = 0.0, 1.0
    else:
        t_stat = slope / se_slope
        p_value = float(2 * stats.t.sf(abs(t_stat), df))
    tcrit = float(stats.t.ppf(1 - alpha / 2, df))

    fitted = pd.Series(icpt + slope * x_all, index=y.index)
    se_mean = np.sqrt(sigma2 * (1.0 / n + (x_all - x_mean) ** 2 / sxx)) * inflate
    ci_low = fitted - tcrit * se_mean
    ci_high = fitted + tcrit * se_mean

    result = {
        "slope_per_year": slope,
        "slope_per_decade": slope * 10,
        "intercept": float(fitted.iloc[0]),  # value of the trend line at the first month
        "ci95_low_per_decade": (slope - tcrit * se_slope) * 10,
        "ci95_high_per_decade": (slope + tcrit * se_slope) * 10,
        "t_stat": float(t_stat),
        "p_value": float(min(max(p_value, 0.0), 1.0)),
        "r_squared": float(r2),
        "n": n,
        "n_effective": float(n_eff),
    }
    return result, fitted, ci_low, ci_high


def _mk_to_dict(res, test: str, slope_per_decade: float) -> dict:
    return {
        "test": test,
        "trend": res.trend if res.trend in ("increasing", "decreasing") else "no trend",
        "p_value": float(res.p),
        "z": float(res.z),
        "tau": float(res.Tau),
        "s": float(res.s),
        "sens_slope_per_decade": float(slope_per_decade),
    }


def mann_kendall(y: pd.Series, deseasonalized: bool) -> dict:
    """Mann-Kendall + Sen's slope, choosing the variant per Architecture.md 9.3."""
    if deseasonalized:
        vals = y.dropna().to_numpy(dtype=float)
        try:
            res = mk.hamed_rao_modification_test(vals)
            if np.isfinite(res.p):
                return _mk_to_dict(res, "hamed_rao", res.slope * 120)  # per month -> per decade
        except (ValueError, ZeroDivisionError, FloatingPointError):
            pass
        res = mk.original_test(vals)
        return _mk_to_dict(res, "original", res.slope * 120)
    # raw monthly with seasonal cycle: compare each calendar month only with itself
    res = mk.seasonal_test(y.to_numpy(dtype=float), period=12)
    return _mk_to_dict(res, "seasonal", res.slope * 10)  # per year -> per decade


def analyze_series(
    series: pd.Series,
    start_year: int,
    end_year: int,
    deseasonalize: bool = True,
    alpha: float = 0.05,
    ratio_scale: bool = True,
) -> TrendComputation:
    """Run the full trend analysis on a monthly series with a complete monthly index."""
    if int(series.notna().sum()) < MIN_VALID_POINTS:
        raise ValueError(f"Need at least {MIN_VALID_POINTS} valid months of data.")

    anomalies = monthly_anomalies(series) if deseasonalize else None
    target = anomalies if anomalies is not None else series

    ols, fitted, ci_low, ci_high = ols_trend(target, alpha)
    mkd = mann_kendall(target, deseasonalize)

    years = end_year - start_year + 1
    total_change = ols["slope_per_year"] * years
    mean_val = float(series.mean())
    percent = None
    if ratio_scale and abs(mean_val) > 1e-6:
        percent = total_change / abs(mean_val) * 100.0

    ols_sig = ols["p_value"] < alpha
    mk_sig = mkd["p_value"] < alpha
    agreement = "both" if ols_sig and mk_sig else "ols_only" if ols_sig else "mk_only" if mk_sig else "neither"

    return TrendComputation(
        target=target,
        anomalies=anomalies,
        fitted=fitted,
        ci_low=ci_low,
        ci_high=ci_high,
        ols=ols,
        mann_kendall=mkd,
        total_change=float(total_change),
        percent_change=None if percent is None else float(percent),
        significant=bool(ols_sig and mk_sig),
        agreement=agreement,
    )
