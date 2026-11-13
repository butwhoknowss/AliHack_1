import numpy as np
import pandas as pd

from app.storage.seed import ALL_VARIABLES, DEMOS, RESOURCES, SEED_VERSION, VARIABLES, ensure_catalog
from app.storage.xlsx_store import XlsxStore, load_catalog, read_catalog_version, read_workbook, write_catalog


def _meta(key: str, resolution: str = "monthly") -> dict:
    return {"cache_key": key, "source": "nasa_power", "variable_id": "T2M", "lat": 1.0, "lon": 2.0,
            "resolution": resolution, "start_year": 2000, "end_year": 2001}


def test_catalog_round_trip(tmp_path):
    assert ensure_catalog(tmp_path) is True
    assert ensure_catalog(tmp_path) is False
    variables, demos, resources = load_catalog(tmp_path)
    assert [v["id"] for v in variables] == [v["id"] for v in ALL_VARIABLES]
    assert all(isinstance(v["seasonal"], bool) for v in variables)
    power = next(v for v in variables if v["id"] == "T2M")
    assert power["provider"] == "power" and power["first_year"] == 1981 and power["scale"] == 1.0
    airs = next(v for v in variables if v["id"] == "AIRS_TSURF")
    assert airs["provider"] == "giovanni" and airs["offset"] == -273.15 and airs["first_year"] == 2003
    assert len(demos) == len(DEMOS)
    assert demos[2]["compare_request"]["variable_id"] == "PRECTOTCORR"
    assert demos[0]["compare_request"] is None
    assert len(resources) == len(RESOURCES) and isinstance(resources[0]["used_in_app"], bool)


def test_catalog_reseeds_when_version_changes(tmp_path):
    write_catalog(tmp_path, VARIABLES[:1], [], [], version="old")
    assert read_catalog_version(tmp_path) == "old"
    assert ensure_catalog(tmp_path) is True
    assert read_catalog_version(tmp_path) == SEED_VERSION
    assert len(load_catalog(tmp_path)[0]) == len(ALL_VARIABLES)


def test_cache_round_trip_and_persistence(tmp_path):
    idx = pd.date_range("2000-01-01", periods=24, freq="MS")
    s = pd.Series(np.arange(24, dtype=float), index=idx)
    s.iloc[3] = np.nan
    store = XlsxStore(tmp_path)
    store.put_cached_many([(_meta("k1"), s)])
    got = store.get_cached("k1", "monthly")
    assert got is not None and np.isnan(got.iloc[3]) and got.iloc[5] == 5.0

    fresh = XlsxStore(tmp_path)  # new process reads from disk
    got2 = fresh.get_cached("k1", "monthly")
    assert got2 is not None and len(got2) == 24 and got2.iloc[23] == 23.0
    assert not list(tmp_path.glob("*.tmp.xlsx"))


def test_cache_ttl_expiry(tmp_path):
    idx = pd.date_range("2000-01-01", periods=12, freq="MS")
    store = XlsxStore(tmp_path, ttl_days=0)
    store.put_cached_many([(_meta("k2"), pd.Series(1.0, index=idx))])
    assert store.get_cached("k2", "monthly") is None


def test_daily_cache_is_memory_only(tmp_path):
    idx = pd.date_range("2000-01-01", periods=10, freq="D")
    store = XlsxStore(tmp_path)
    store.put_cached_many([(_meta("d1", "daily"), pd.Series(1.0, index=idx))])
    assert store.get_cached("d1", "daily") is not None
    assert not (tmp_path / "cache.xlsx").exists()


def test_corrupt_workbook_is_moved_aside(tmp_path):
    bad = tmp_path / "cache.xlsx"
    bad.write_bytes(b"not an excel file")
    assert read_workbook(bad) == {}
    assert not bad.exists()
    assert list(tmp_path.glob("cache.corrupt-*.xlsx"))


def test_save_and_load_analysis(tmp_path):
    store = XlsxStore(tmp_path)
    row = {"analysis_id": "a" * 32, "created_at": "2026-01-01", "variable_id": "T2M", "region_json": "{}",
           "start_year": 2000, "end_year": 2010, "resolution": "monthly", "deseasonalize": True, "alpha": 0.05,
           "ols_slope_per_decade": 0.1, "ols_p": 0.01, "mk_p": 0.02, "sens_slope_per_decade": 0.1,
           "significant": True, "verdict": "x", "request_json": '{"variable_id": "T2M"}'}
    df = pd.DataFrame({"analysis_id": "a" * 32, "date": ["2000-01-01"], "value": [1.0], "anomaly": [0.0]})
    store.save_analysis(row, df)
    store.save_analysis({**row, "analysis_id": "b" * 32}, df.assign(analysis_id="b" * 32))
    assert store.load_analysis_request("a" * 32) == {"variable_id": "T2M"}
    assert store.load_analysis_request("c" * 32) is None
