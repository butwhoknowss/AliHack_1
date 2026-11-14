import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.models.requests import last_complete_year
from app.services.places import base_name, distance_km, place_label

from .conftest import POWER_URL, WEATHER_BASE, power_payload

EL_CHORRO = {"name": "El Chorro", "region": "Arequipa", "country": "Peru", "lat": -16.65, "lon": -72.70}
END = last_complete_year()


def test_distance():
    assert distance_km(0, 0, 0, 1) == pytest.approx(111.2, abs=0.5)
    assert distance_km(-17, -72.9, -17, -72.9) == 0


def test_labels_are_honest_about_distance():
    assert place_label(EL_CHORRO, -17.0, -72.9)[0] == "El Chorro, Peru"            # ~44 km: same grid cell
    assert place_label(EL_CHORRO, -17.5, -73.5)[0] == "near El Chorro, Peru"       # ~125 km
    far, d = place_label(EL_CHORRO, -17.0, -80.0)
    assert far.startswith("≈") and far.endswith("km from El Chorro, Peru") and d > 700
    assert place_label(EL_CHORRO, -17.5, -73.5, "bbox")[0] == "area around El Chorro, Peru"


def test_country_shortening_and_cap():
    fbx = {"name": "Fairbanks", "region": "Alaska", "country": "United States of America", "lat": 64.84, "lon": -147.72}
    assert base_name(fbx) == "Fairbanks, Alaska, USA"
    long = {**EL_CHORRO, "name": "X" * 200}
    assert len(place_label(long, -16.65, -72.70)[0]) == 120


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


@respx.mock
def test_reverse_endpoint(client):
    route = respx.get(f"{WEATHER_BASE}/search.json").mock(return_value=httpx.Response(200, json=[EL_CHORRO]))
    r = client.get("/api/locations/reverse", params={"lat": -17.0, "lon": -72.9})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["label"] == "El Chorro, Peru" and body["distance_km"] == pytest.approx(44, abs=2)
    assert route.calls[0].request.url.params["q"] == "-17.0000,-72.9000"
    box = client.get("/api/locations/reverse", params={"lat": -17.0, "lon": -72.9, "kind": "bbox"}).json()
    assert box["label"] == "area around El Chorro, Peru"


@respx.mock
def test_reverse_nothing_found(client):
    respx.get(f"{WEATHER_BASE}/search.json").mock(return_value=httpx.Response(200, json=[]))
    assert client.get("/api/locations/reverse", params={"lat": 0, "lon": -140}).status_code == 404


@respx.mock
def test_verdict_uses_place_name(client):
    respx.get(POWER_URL).mock(return_value=httpx.Response(200, json=power_payload("WS2M", END - 29, END)))
    body = {"variable_id": "WS2M", "start_year": END - 29, "end_year": END, "save": False,
            "region": {"type": "point", "lat": -17.0, "lon": -72.9, "name": "El Chorro, Peru"}}
    verdict = client.post("/api/analyze", json=body).json()["trend"]["verdict"]
    assert "El Chorro, Peru" in verdict
