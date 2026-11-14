import httpx
import respx
from fastapi.testclient import TestClient

from app.models import Region
from app.models.requests import fmt_lat, fmt_lon, last_complete_year

from .conftest import POWER_URL, power_payload

END = last_complete_year()
START = END - 29


def test_hemisphere_letters_instead_of_minus_signs():
    assert fmt_lat(-19.5) == "19.5°S" and fmt_lat(14.5) == "14.5°N" and fmt_lat(0) == "0.0°"
    assert fmt_lon(-75.4) == "75.4°W" and fmt_lon(70.4) == "70.4°E" and fmt_lon(-180) == "180.0°"
    assert fmt_lat(-0.04) == "0.0°"  # rounds to zero -> no hemisphere


def test_region_labels():
    box = Region(type="bbox", south=-19.5, north=-14.5, west=-75.4, east=-70.4)
    assert box.label() == "box 19.5°S–14.5°S, 75.4°W–70.4°W"
    across = Region(type="bbox", south=-2, north=3, west=-1, east=2)
    assert across.label() == "box 2.0°S–3.0°N, 1.0°W–2.0°E"
    assert Region(type="point", lat=64.8, lon=-147.7).label() == "64.80°N, 147.70°W"
    assert Region(type="point", lat=1, lon=2, name="Somewhere").label() == "Somewhere"


@respx.mock
def test_verdict_uses_hemisphere_coordinates(app):
    respx.get(POWER_URL).mock(return_value=httpx.Response(200, json=power_payload("T2M", START, END)))
    body = {"variable_id": "T2M", "start_year": START, "end_year": END, "save": False,
            "region": {"type": "bbox", "south": -19.5, "north": -14.5, "west": -75.4, "east": -70.4}}
    with TestClient(app) as c:
        verdict = c.post("/api/analyze", json=body).json()["trend"]["verdict"]
    assert "19.5°S–14.5°S, 75.4°W–70.4°W" in verdict
    assert "-75.4" not in verdict and "..-" not in verdict
