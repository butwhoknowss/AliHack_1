from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.models import Region
from app.services.next_steps import MAX_SUGGESTIONS, in_or_near_canada, suggest_next_steps
from app.storage.seed import RESOURCE_STEPS, RESOURCES


def fake_result(variable_id="T2M", provider="power", agreement="both", slope=0.3,
                region=None, deseasonalize=True):
    region = region or Region(type="point", lat=10.0, lon=10.0, name="Test place")
    return SimpleNamespace(
        variable=SimpleNamespace(id=variable_id, name=f"Var {variable_id}", provider=provider),
        region=region,
        trend=SimpleNamespace(agreement=agreement, ols=SimpleNamespace(slope_per_decade=slope)),
        period=(1981, 2020),
        deseasonalize=deseasonalize,
    )


def keys(res):
    return [n.key for n in suggest_next_steps(RESOURCES, res)]


# ------------------------------------------------------------------ relationship data

def test_every_resource_has_step_and_valid_links():
    all_keys = {r["key"] for r in RESOURCES}
    steps = {s["step"] for s in RESOURCE_STEPS}
    assert len(all_keys) == len(RESOURCES)  # keys are unique
    for r in RESOURCES:
        assert r["step"] in steps, r["key"]
        for key, why in r["related"]:
            assert key in all_keys and key != r["key"] and why


# ------------------------------------------------------------------ suggestions

def test_temperature_suggests_station_check_and_tests():
    k = keys(fake_result("T2M", agreement="both"))
    assert k[0] == "cdo" and "trendtests" in k
    assert len(k) <= MAX_SUGGESTIONS and len(set(k)) == len(k)


def test_not_significant_points_to_significance_guide():
    assert "significance" in keys(fake_result("T2M", agreement="neither"))


def test_satellite_runoff_links_giovanni_and_swot():
    k = keys(fake_result("GLDAS_RUNOFF", provider="giovanni", agreement="mk_only"))
    assert "giovanni" in k and "swot" in k and "cdo" not in k


def test_canadian_region_suggests_canadian_resources():
    yukon = Region(type="bbox", south=60, west=-137, north=63, east=-133, name="Yukon")
    k = keys(fake_result("GWETTOP", region=yukon))
    assert "geo" in k and "rcm" in k


def test_canada_box_test():
    assert in_or_near_canada(Region(type="point", lat=45.5, lon=-73.6))       # Montreal
    assert in_or_near_canada(Region(type="point", lat=64.8, lon=-147.7)) is False  # Fairbanks, Alaska
    assert in_or_near_canada(Region(type="point", lat=40.0, lon=-100.0)) is False  # Kansas
    assert in_or_near_canada(Region(type="point", lat=33.0, lon=-112.0)) is False  # Arizona


def test_missing_resources_are_skipped():
    assert suggest_next_steps([], fake_result()) == []


# ------------------------------------------------------------------ API

def test_resources_carry_relationships(app):
    with TestClient(app) as c:
        res = c.get("/api/resources").json()
        steps = c.get("/api/resources/steps").json()
    assert [s["step"] for s in steps] == ["data", "test", "check", "explain"]
    giovanni = next(r for r in res if r["key"] == "giovanni")
    assert giovanni["step"] == "data" and any(link["key"] == "hydrology" for link in giovanni["related"])
