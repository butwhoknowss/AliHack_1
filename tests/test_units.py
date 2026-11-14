import io

import httpx
import pandas as pd
import pytest
import respx
from fastapi.testclient import TestClient

from app.errors import DataQualityError
from app.models.requests import last_complete_year
from app.services.units import UNIT_OPTIONS, options_for, resolve
from app.storage.seed import ALL_VARIABLES

from .conftest import POWER_URL, power_payload

END = last_complete_year()
START = END - 29


def convert(base, unit_id, value):
    opt = resolve(base, unit_id)
    return value * opt.factor + opt.offset


# ------------------------------------------------------------------ conversion table

def test_known_conversions():
    assert convert("°C", "degF", 0) == pytest.approx(32)
    assert convert("°C", "degF", 100) == pytest.approx(212)
    assert convert("°C", "K", 0) == pytest.approx(273.15)
    assert convert("m/s", "km_h", 1) == pytest.approx(3.6)
    assert convert("m/s", "mph", 10) == pytest.approx(22.369, abs=1e-3)
    assert convert("kPa", "hPa", 101.325) == pytest.approx(1013.25)
    assert convert("kPa", "inHg", 101.325) == pytest.approx(29.92, abs=0.01)
    assert convert("MJ/m²/day", "kWh_m2_day", 3.6) == pytest.approx(1.0)
    assert convert("MJ/m²/day", "W_m2", 1) == pytest.approx(11.574, abs=1e-3)
    assert convert("mm/day", "mm_year", 1) == pytest.approx(365.25)
    assert convert("mm/day", "in_year", 1) == pytest.approx(14.38, abs=0.01)
    assert convert("fraction (0–1)", "percent", 0.25) == pytest.approx(25)


def test_base_unit_is_first_and_unknown_unit_rejected():
    assert resolve("°C", None).label == "°C" and resolve("°C", "base").factor == 1.0
    assert [o.label for o in options_for("DU")] == ["DU"]  # no extra options
    with pytest.raises(DataQualityError, match="Available units"):
        resolve("DU", "degF")


def test_every_catalog_unit_with_options_matches_exactly():
    catalog_units = {v["units"] for v in ALL_VARIABLES}
    assert set(UNIT_OPTIONS) <= catalog_units  # a typo in a key would silently offer nothing
    for opts in UNIT_OPTIONS.values():
        assert len({o.id for o in opts}) == len(opts) and all(o.id != "base" for o in opts)


# ------------------------------------------------------------------ API

@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def body(**over):
    b = {"variable_id": "T2M", "region": {"type": "point", "lat": 64.8, "lon": -147.7, "name": "Fairbanks"},
         "start_year": START, "end_year": END}
    return {**b, **over}


def test_variables_list_unit_options(client):
    t2m = client.get("/api/variables/T2M").json()
    assert t2m["base_units"] == "°C"
    assert [o["id"] for o in t2m["unit_options"]] == ["base", "degF", "K"]


@respx.mock
def test_fahrenheit_scales_trend_but_not_significance(client):
    respx.get(POWER_URL).mock(return_value=httpx.Response(200, json=power_payload("T2M", START, END, slope_per_year=0.05)))
    c = client.post("/api/analyze", json=body()).json()
    f = client.post("/api/analyze", json=body(units="degF")).json()
    assert f["variable"]["units"] == "°F" and f["variable"]["base_units"] == "°C"
    assert f["trend"]["ols"]["slope_per_decade"] == pytest.approx(1.8 * c["trend"]["ols"]["slope_per_decade"], rel=1e-4)
    assert f["trend"]["total_change"] == pytest.approx(1.8 * c["trend"]["total_change"], rel=1e-4)
    assert f["trend"]["ols"]["p_value"] == pytest.approx(c["trend"]["ols"]["p_value"], rel=1e-6)
    assert f["trend"]["mann_kendall"]["p_value"] == pytest.approx(c["trend"]["mann_kendall"]["p_value"], rel=1e-6)
    assert f["trend"]["significant"] == c["trend"]["significant"]
    assert "°F" in f["trend"]["verdict"]
    assert f["series"][6]["value"] == pytest.approx(c["series"][6]["value"] * 1.8 + 32, abs=1e-3)

    # saved request keeps the unit: export columns are in °F
    x = client.get(f"/api/export/{f['analysis_id']}", params={"format": "xlsx"})
    assert x.status_code == 200
    sheets = pd.read_excel(io.BytesIO(x.content), sheet_name=None)
    assert any("value (°F)" in df.columns for df in sheets.values())


def test_invalid_unit_is_422(client):
    r = client.post("/api/analyze", json=body(units="furlongs"))
    assert r.status_code == 422 and "Available units" in r.json()["detail"]
