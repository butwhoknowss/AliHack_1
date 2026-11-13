import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.models.requests import last_complete_year

from .conftest import POWER_URL, WEATHER_BASE, power_payload

END = last_complete_year()
START = END - 29


def _analyze_body(**over):
    body = {
        "variable_id": "T2M",
        "region": {"type": "point", "lat": 64.8, "lon": -147.7, "name": "Fairbanks"},
        "start_year": START,
        "end_year": END,
        "deseasonalize": True,
    }
    body.update(over)
    return body


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def test_variables_and_demos(client):
    r = client.get("/api/variables")
    assert r.status_code == 200
    ids = [v["id"] for v in r.json()]
    assert "T2M" in ids and "PRECTOTCORR" in ids
    assert client.get("/api/variables/T2M").json()["units"] == "°C"
    assert client.get("/api/variables/NOPE").status_code == 404
    assert client.get("/api/variables", params={"category": "Land"}).json()[0]["category"] == "Land"
    demos = client.get("/api/demos").json()
    assert len(demos) == 3 and demos[2]["compare_request"] is not None


@respx.mock
def test_analyze_happy_path_then_reload_and_export(client):
    route = respx.get(POWER_URL).mock(
        return_value=httpx.Response(200, json=power_payload("T2M", START, END, slope_per_year=0.05))
    )
    r = client.post("/api/analyze", json=_analyze_body())
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["trend"]["significant"] is True
    assert data["trend"]["ols"]["slope_per_decade"] == pytest.approx(0.5, abs=0.1)
    assert data["trend"]["percent_change"] is None  # temperature is not ratio-scale
    assert len(data["series"]) == 30 * 12
    assert data["series"][0]["anomaly"] is not None
    assert "Fairbanks" in data["trend"]["verdict"]
    next_keys = [n["key"] for n in data["next_steps"]]
    assert next_keys and next_keys[0] == "cdo"  # temperature -> compare with weather stations first
    assert route.call_count == 1

    # second call hits the xlsx cache, not the network
    assert client.post("/api/analyze", json=_analyze_body(save=False)).status_code == 200
    assert route.call_count == 1

    aid = data["analysis_id"]
    again = client.get(f"/api/analyses/{aid}")
    assert again.status_code == 200 and again.json()["analysis_id"] == aid

    x = client.get(f"/api/export/{aid}", params={"format": "xlsx"})
    assert x.status_code == 200 and x.content[:2] == b"PK"
    c = client.get(f"/api/export/{aid}", params={"format": "csv"})
    assert c.status_code == 200 and "trend line" in c.content.decode("utf-8-sig")


@respx.mock
def test_bbox_uses_multiple_points(client):
    route = respx.get(POWER_URL).mock(
        return_value=httpx.Response(200, json=power_payload("T2M", START, END))
    )
    body = _analyze_body(region={"type": "bbox", "south": 60, "west": -150, "north": 62, "east": -148})
    r = client.post("/api/analyze", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["n_sample_points"] == 4
    assert route.call_count == 4


def test_validation_errors(client):
    assert client.post("/api/analyze", json=_analyze_body(start_year=END - 3)).status_code == 422
    assert client.post("/api/analyze", json=_analyze_body(end_year=END + 1)).status_code == 422
    big = _analyze_body(region={"type": "bbox", "south": 0, "west": 0, "north": 10, "east": 2})
    r = client.post("/api/analyze", json=big)
    assert r.status_code == 422 and "too large" in r.json()["detail"]
    assert client.post("/api/analyze", json=_analyze_body(variable_id="NOPE")).status_code == 404
    assert client.get("/api/analyses/not-an-id").status_code == 422
    assert client.get("/api/analyses/" + "f" * 32).status_code == 404


@respx.mock
def test_upstream_error_maps_to_502(client):
    respx.get(POWER_URL).mock(return_value=httpx.Response(400, json={"messages": ["bad"]}))
    r = client.post("/api/analyze", json=_analyze_body(region={"type": "point", "lat": 1.0, "lon": 1.0}))
    assert r.status_code == 502


@respx.mock
def test_all_missing_data_is_422(client):
    payload = power_payload("T2M", START, END)
    vals = payload["properties"]["parameter"]["T2M"]
    for k in vals:
        vals[k] = -999.0
    respx.get(POWER_URL).mock(return_value=httpx.Response(200, json=payload))
    r = client.post("/api/analyze", json=_analyze_body(region={"type": "point", "lat": 2.0, "lon": 2.0}))
    assert r.status_code == 422


@respx.mock
def test_location_search_and_current_weather(client):
    respx.get(f"{WEATHER_BASE}/search.json").mock(
        return_value=httpx.Response(200, json=[{"name": "Fairbanks", "region": "Alaska", "country": "USA",
                                                "lat": 64.84, "lon": -147.72}])
    )
    respx.get(f"{WEATHER_BASE}/current.json").mock(
        return_value=httpx.Response(200, json={
            "location": {"name": "Fairbanks", "country": "USA", "localtime": "2026-01-01 10:00"},
            "current": {"temp_c": -20.0, "feelslike_c": -25.0, "humidity": 70, "wind_kph": 5.0,
                        "precip_mm": 0.0, "condition": {"text": "Snow", "icon": "//cdn.weatherapi.com/x.png"}},
        })
    )
    r = client.get("/api/locations/search", params={"q": "Fairbanks"})
    assert r.status_code == 200 and r.json()[0]["lat"] == 64.84
    w = client.get("/api/weather/current", params={"lat": 64.84, "lon": -147.72})
    assert w.status_code == 200 and w.json()["icon"].startswith("https://")


@respx.mock
def test_location_not_found(client):
    respx.get(f"{WEATHER_BASE}/search.json").mock(return_value=httpx.Response(200, json=[]))
    assert client.get("/api/locations/search", params={"q": "zzzzzz"}).status_code == 404


def test_cors_allows_live_server(client):
    r = client.options(
        "/api/variables",
        headers={"Origin": "http://127.0.0.1:5500", "Access-Control-Request-Method": "GET"},
    )
    assert r.headers.get("access-control-allow-origin") == "http://127.0.0.1:5500"
