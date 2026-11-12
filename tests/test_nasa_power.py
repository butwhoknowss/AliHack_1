import httpx
import numpy as np
import pytest
import respx

from app.errors import UpstreamError
from app.sources.nasa_power import NasaPowerSource, parse_power_payload

from .conftest import POWER_URL, power_payload


def test_parse_drops_month_13_and_fill_values():
    payload = power_payload("T2M", 2000, 2001, fill_months=("200005",))
    s = parse_power_payload(payload, "T2M", "monthly")
    assert len(s) == 24  # 13th "month" (annual mean) removed
    assert np.isnan(s.loc["2000-05-01"])
    assert s.index.is_monotonic_increasing


def test_parse_daily_keys():
    payload = {"properties": {"parameter": {"T2M": {"20200101": 1.0, "20200102": -999}}}}
    s = parse_power_payload(payload, "T2M", "daily")
    assert len(s) == 2 and np.isnan(s.iloc[1])


def test_parse_missing_parameter_raises():
    with pytest.raises(UpstreamError):
        parse_power_payload({"properties": {"parameter": {}}}, "T2M", "monthly")


@pytest.mark.asyncio
@respx.mock
async def test_fetch_retries_then_succeeds():
    route = respx.get(POWER_URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json=power_payload("T2M", 2000, 2010))]
    )
    async with httpx.AsyncClient() as client:
        src = NasaPowerSource(client, "https://power.larc.nasa.gov/api", retries=2)
        src_sleep = pytest.MonkeyPatch()
        src_sleep.setattr("asyncio.sleep", _no_sleep)
        try:
            s = await src.fetch_point("T2M", 10, 20, 2000, 2010, "monthly")
        finally:
            src_sleep.undo()
    assert route.call_count == 2
    assert len(s) == 11 * 12


@pytest.mark.asyncio
@respx.mock
async def test_fetch_client_error_not_retried():
    route = respx.get(POWER_URL).mock(return_value=httpx.Response(422, json={"messages": ["bad"]}))
    async with httpx.AsyncClient() as client:
        src = NasaPowerSource(client, "https://power.larc.nasa.gov/api")
        with pytest.raises(UpstreamError):
            await src.fetch_point("T2M", 10, 20, 2000, 2010, "monthly")
    assert route.call_count == 1


async def _no_sleep(_):
    return None
