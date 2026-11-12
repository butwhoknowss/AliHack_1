import numpy as np
import pandas as pd
import pytest

from app.services.trend import analyze_series, decimal_year, monthly_anomalies


def synthetic(slope_per_year: float, years: int = 40, noise: float = 0.5, ar: float = 0.3, seed: int = 1,
              amp: float = 8.0) -> pd.Series:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("1981-01-01", periods=years * 12, freq="MS")
    t = decimal_year(idx) - 1981
    e = np.zeros(len(idx))
    for i in range(1, len(idx)):
        e[i] = ar * e[i - 1] + rng.normal(0, noise)
    seasonal = amp * np.sin(2 * np.pi * (idx.month.to_numpy() - 1) / 12)
    return pd.Series(10 + slope_per_year * t + seasonal + e, index=idx)


def test_recovers_known_slope_and_is_significant():
    s = synthetic(0.05)  # 0.5 per decade
    res = analyze_series(s, 1981, 2020, deseasonalize=True)
    assert res.ols["slope_per_decade"] == pytest.approx(0.5, abs=0.05)
    assert res.mann_kendall["sens_slope_per_decade"] == pytest.approx(0.5, abs=0.08)
    assert res.mann_kendall["test"] == "hamed_rao"
    assert res.significant and res.agreement == "both"
    assert res.ols["ci95_low_per_decade"] < 0.5 < res.ols["ci95_high_per_decade"]
    assert res.total_change == pytest.approx(0.05 * 40, abs=0.25)


def test_zero_slope_is_not_significant():
    s = synthetic(0.0, seed=7)
    res = analyze_series(s, 1981, 2020, deseasonalize=True)
    assert not res.significant
    assert abs(res.ols["slope_per_decade"]) < 0.1


def test_negative_trend_direction():
    res = analyze_series(synthetic(-0.04), 1981, 2020)
    assert res.ols["slope_per_decade"] < 0
    assert res.mann_kendall["trend"] == "decreasing"


def test_seasonal_mk_when_not_deseasonalized():
    res = analyze_series(synthetic(0.05), 1981, 2020, deseasonalize=False)
    assert res.mann_kendall["test"] == "seasonal"
    assert res.mann_kendall["sens_slope_per_decade"] == pytest.approx(0.5, abs=0.08)
    assert res.anomalies is None


def test_handles_gaps():
    s = synthetic(0.05)
    s.iloc[[3, 50, 51, 200, 333]] = np.nan
    res = analyze_series(s, 1981, 2020)
    assert np.isfinite(res.ols["p_value"])
    assert res.fitted.notna().all()


def test_anomalies_have_zero_monthly_mean():
    a = monthly_anomalies(synthetic(0.0))
    assert a.groupby(a.index.month).mean().abs().max() < 1e-9


def test_autocorrelation_reduces_effective_n():
    res = analyze_series(synthetic(0.02, ar=0.8), 1981, 2020)
    assert res.ols["n_effective"] < res.ols["n"] * 0.5


def test_percent_change_skipped_for_non_ratio():
    res = analyze_series(synthetic(0.05), 1981, 2020, ratio_scale=False)
    assert res.percent_change is None


def test_too_little_data_raises():
    s = synthetic(0.05, years=1)
    with pytest.raises(ValueError):
        analyze_series(s, 1981, 1981)
