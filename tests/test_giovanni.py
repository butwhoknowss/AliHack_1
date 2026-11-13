import httpx
import numpy as np
import pytest
import respx
from fastapi.testclient import TestClient

from app.errors import UpstreamError
from app.main import create_app
from app.models.requests import last_complete_year
from app.sources.giovanni import GiovanniSource, parse_giovanni_csv, parse_signin_token, to_month_start

from .conftest import GIOVANNI_BASE, giovanni_csv

EDL_AUTHORIZE = "https://urs.earthdata.nasa.gov/oauth/authorize"
END = last_complete_year()


def mock_signin(token: str = "giovanni-token-123"):
    """Giovanni /signin -> Earthdata authorize (basic auth) -> /gettoken returns the token."""
    respx.get(f"{GIOVANNI_BASE}/signin").mock(
        return_value=httpx.Response(302, headers={"location": f"{EDL_AUTHORIZE}?client_id=x&redirect_uri=y"})
    )
    authorize = respx.get(url__startswith=EDL_AUTHORIZE).mock(
        return_value=httpx.Response(302, headers={"location": f"{GIOVANNI_BASE}/gettoken?code=abc"})
    )
    # real Giovanni answer (checked live): JSON with the token and its lifetime
    respx.get(url__startswith=f"{GIOVANNI_BASE}/gettoken").mock(
        return_value=httpx.Response(200, json={"expires_in": 86400, "token": token})
    )
    return authorize


# ------------------------------------------------------------------ parsing

def test_parse_csv_skips_metadata_and_fills():
    s = parse_giovanni_csv(giovanni_csv(2010, 2011, fill_months=("201003",)))
    assert len(s) == 23  # one fill value dropped
    assert s.index[0].year == 2010 and s.index.is_monotonic_increasing


def test_parse_csv_undef_fill_key():
    lines = giovanni_csv(2010, 2010).splitlines()
    lines.insert(lines.index("Timestamp (UTC),Data"), "undef,-1234.5")
    lines[-1] = lines[-1].split(",")[0] + ",-1234.5"
    text = "\n".join(lines) + "\n"
    assert len(parse_giovanni_csv(text)) == 11


def test_parse_signin_token_formats():
    assert parse_signin_token('{"expires_in": 3600, "token": "abc.def"}') == ("abc.def", 3600.0)
    assert parse_signin_token('"abc.def"')[0] == "abc.def"
    assert parse_signin_token("<!DOCTYPE html><html>login</html>")[0] is None
    assert parse_signin_token('{"message": "nope"}')[0] is None


def test_parse_csv_without_table_raises():
    with pytest.raises(UpstreamError):
        parse_giovanni_csv("some,error\nnothing here\n")


def test_daily_values_average_to_months():
    import pandas as pd

    idx = pd.date_range("2020-01-01", "2020-02-29", freq="D")
    s = pd.Series(np.where(idx.month == 1, 1.0, 3.0), index=idx)
    m = to_month_start(s)
    assert list(m.index.strftime("%Y-%m-%d")) == ["2020-01-01", "2020-02-01"]
    assert m.tolist() == [1.0, 3.0]


# ------------------------------------------------------------------ source

@pytest.mark.asyncio
@respx.mock
async def test_signin_flow_and_unit_conversion():
    authorize = mock_signin()
    ts = respx.get(f"{GIOVANNI_BASE}/timeseries").mock(
        return_value=httpx.Response(200, text=giovanni_csv(2010, 2011, base=280.0))
    )
    async with httpx.AsyncClient() as client:
        src = GiovanniSource(client, GIOVANNI_BASE, username="u", password="p")
        s = await src.fetch_point("AIRS_TSURF", 40, -100, 2010, 2011, provider_id="X", offset=-273.15)
        await src.fetch_point("AIRS_TSURF", 41, -100, 2010, 2011, provider_id="X", offset=-273.15)
    assert authorize.call_count == 1  # token cached after the first sign-in
    assert authorize.calls[0].request.headers["authorization"].startswith("Basic ")
    assert ts.calls[0].request.headers["authorizationtoken"] == "giovanni-token-123"
    assert ts.calls[0].request.url.params["location"] == "[40.0000,-100.0000]"
    assert 0 < s.mean() < 15  # kelvin converted to °C


@pytest.mark.asyncio
@respx.mock
async def test_bad_login_gives_helpful_error():
    respx.get(f"{GIOVANNI_BASE}/timeseries").mock(return_value=httpx.Response(401, json={"message": "no"}))
    async with httpx.AsyncClient() as client:
        src = GiovanniSource(client, GIOVANNI_BASE, token="edl-token")
        with pytest.raises(UpstreamError, match="Earthdata"):
            await src.fetch_point("X", 1, 2, 2010, 2011, provider_id="X")
        assert await src.verify("X") is False


@pytest.mark.asyncio
@respx.mock
async def test_approval_page_gives_specific_error():
    respx.get(f"{GIOVANNI_BASE}/signin").mock(
        return_value=httpx.Response(302, headers={"location": f"{EDL_AUTHORIZE}?client_id=x"})
    )
    respx.get(url__startswith=EDL_AUTHORIZE).mock(return_value=httpx.Response(200, text="<html>approve</html>"))
    async with httpx.AsyncClient() as client:
        src = GiovanniSource(client, GIOVANNI_BASE, username="u", password="p")
        assert await src.verify("X") is False
    assert "approval page" in src.last_error


@pytest.mark.asyncio
@respx.mock
async def test_invalid_data_id_is_not_a_login_error():
    mock_signin()
    respx.get(f"{GIOVANNI_BASE}/timeseries").mock(return_value=httpx.Response(
        403, json={"code": "400", "message": "Bad or missing input", "context": "Data parameter is invalid"}
    ))
    async with httpx.AsyncClient() as client:
        src = GiovanniSource(client, GIOVANNI_BASE, username="u", password="p")
        with pytest.raises(UpstreamError, match="does not recognise the data ID 'BAD_ID'"):
            await src.fetch_point("X", 1, 2, 2010, 2011, provider_id="BAD_ID")


@pytest.mark.asyncio
async def test_not_configured():
    async with httpx.AsyncClient() as client:
        src = GiovanniSource(client, GIOVANNI_BASE)
        assert not src.configured
        assert await src.verify("X") is False


# ------------------------------------------------------------------ API

def test_variables_unavailable_without_login(app):
    with TestClient(app) as c:
        vars_ = {v["id"]: v for v in c.get("/api/variables").json()}
        assert vars_["T2M"]["available"] is True
        g = vars_["GPM_PRECIP"]
        assert g["provider"] == "giovanni" and g["available"] is False and "Earthdata" in g["unavailable_reason"]
        body = {"variable_id": "GPM_PRECIP", "region": {"type": "point", "lat": 1, "lon": 1},
                "start_year": 2005, "end_year": END}
        r = c.post("/api/analyze", json=body)
        assert r.status_code == 422 and "Earthdata" in r.json()["detail"]
        h = c.get("/api/health").json()
        assert h["giovanni_configured"] is False


@respx.mock
def test_giovanni_analysis_end_to_end(giovanni_settings):
    mock_signin()
    respx.get(f"{GIOVANNI_BASE}/timeseries").mock(
        return_value=httpx.Response(200, text=giovanni_csv(2003, END, slope_per_year=0.05, base=280.0))
    )
    with TestClient(create_app(giovanni_settings)) as c:
        v = c.get("/api/variables/AIRS_TSURF").json()
        assert v["first_year"] == 2003
        too_early = {"variable_id": "AIRS_TSURF", "region": {"type": "point", "lat": 40, "lon": -100},
                     "start_year": 1990, "end_year": END}
        r = c.post("/api/analyze", json=too_early)
        assert r.status_code == 422 and "2003" in r.json()["detail"]

        daily = {**too_early, "start_year": 2005, "resolution": "daily"}
        assert c.post("/api/analyze", json=daily).status_code == 422

        ok = {**too_early, "start_year": 2005,
              "region": {"type": "bbox", "south": 38, "west": -104, "north": 43, "east": -99}}
        r = c.post("/api/analyze", json=ok)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["n_sample_points"] == 9  # Giovanni boxes capped at 3 x 3
        assert data["trend"]["ols"]["slope_per_decade"] == pytest.approx(0.5, abs=0.15)
        assert data["trend"]["percent_change"] is None  # temperature
        assert "Giovanni" in data["source_citation"]


def test_resources_endpoint(app):
    with TestClient(app) as c:
        res = c.get("/api/resources").json()
    titles = [r["title"] for r in res]
    assert "Giovanni" in titles and "KNMI Climate Explorer" in titles
    assert all(r["url"].startswith("https://") for r in res)
    assert any(r["used_in_app"] for r in res)
