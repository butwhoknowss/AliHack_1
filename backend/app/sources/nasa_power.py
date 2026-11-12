"""NASA POWER adapter (https://power.larc.nasa.gov/docs/services/api/).

Gotchas handled here:
- monthly keys are YYYYMM and month 13 is the ANNUAL mean -> dropped;
- the fill value (-999, also given in header.fill_value) -> NaN;
- the API is slow for long ranges and rate-limits -> semaphore + retries.
"""

from __future__ import annotations

import asyncio
import logging
import math
from typing import Literal

import httpx
import numpy as np
import pandas as pd

from ..errors import UpstreamError, UpstreamTimeout

log = logging.getLogger(__name__)

DEFAULT_FILL = -999.0
RETRY_STATUS = {429, 500, 502, 503, 504}


class NasaPowerSource:
    name = "nasa_power"
    citation = (
        "These data were obtained from the NASA Langley Research Center (LaRC) POWER Project "
        "funded through the NASA Earth Science/Applied Science Program."
    )

    def __init__(self, client: httpx.AsyncClient, base_url: str, max_concurrency: int = 4, retries: int = 2):
        self.client = client
        self.base_url = base_url.rstrip("/")
        self.sem = asyncio.Semaphore(max_concurrency)
        self.retries = retries

    async def _get_json(self, url: str, params: dict) -> dict:
        delay = 1.0
        for attempt in range(self.retries + 1):
            try:
                async with self.sem:
                    resp = await self.client.get(url, params=params)
            except httpx.TimeoutException as exc:
                if attempt == self.retries:
                    raise UpstreamTimeout("NASA POWER did not respond in time.") from exc
            except httpx.HTTPError as exc:
                if attempt == self.retries:
                    raise UpstreamError(f"Could not reach NASA POWER: {exc.__class__.__name__}") from exc
            else:
                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except ValueError as exc:
                        raise UpstreamError("NASA POWER returned invalid JSON.") from exc
                if resp.status_code not in RETRY_STATUS or attempt == self.retries:
                    raise UpstreamError(f"NASA POWER returned HTTP {resp.status_code}: {_short_message(resp)}")
            log.warning("NASA POWER attempt %d failed; retrying in %.1fs", attempt + 1, delay)
            await asyncio.sleep(delay)
            delay *= 2
        raise UpstreamError("NASA POWER request failed.")  # pragma: no cover - loop always returns/raises

    async def fetch_point(
        self,
        variable_id: str,
        lat: float,
        lon: float,
        start_year: int,
        end_year: int,
        resolution: Literal["monthly", "daily"] = "monthly",
    ) -> pd.Series:
        params = {
            "parameters": variable_id,
            "community": "AG",
            "latitude": f"{lat:.4f}",
            "longitude": f"{lon:.4f}",
            "format": "JSON",
        }
        if resolution == "monthly":
            params.update(start=str(start_year), end=str(end_year))
        else:
            params.update(start=f"{start_year}0101", end=f"{end_year}1231")
        url = f"{self.base_url}/temporal/{resolution}/point"
        payload = await self._get_json(url, params)
        return parse_power_payload(payload, variable_id, resolution)

    async def ping(self) -> bool:
        """Cheap reachability check: one year of one parameter at one point."""
        params = {
            "parameters": "T2M", "community": "AG", "latitude": "0", "longitude": "0",
            "start": "2020", "end": "2020", "format": "JSON",
        }
        try:
            resp = await self.client.get(f"{self.base_url}/temporal/monthly/point", params=params, timeout=20)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False


def _short_message(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        msgs = body.get("messages") or body.get("detail") or body.get("errors")
        if msgs:
            return str(msgs)[:300]
    except ValueError:
        pass
    return resp.text[:300]


def parse_power_payload(payload: dict, variable_id: str, resolution: str) -> pd.Series:
    """Convert a POWER point JSON payload into a clean float Series."""
    try:
        values: dict = payload["properties"]["parameter"][variable_id]
    except (KeyError, TypeError) as exc:
        raise UpstreamError(f"NASA POWER response has no data for {variable_id}.") from exc

    fill = payload.get("header", {}).get("fill_value", DEFAULT_FILL)
    try:
        fill = float(fill)
    except (TypeError, ValueError):
        fill = DEFAULT_FILL

    dates: list[pd.Timestamp] = []
    data: list[float] = []
    for key, raw in values.items():
        key = str(key)
        if resolution == "monthly":
            if len(key) != 6 or key[4:] == "13":  # month 13 = annual mean
                continue
            ts = pd.Timestamp(year=int(key[:4]), month=int(key[4:]), day=1)
        else:
            if len(key) != 8:
                continue
            ts = pd.Timestamp(year=int(key[:4]), month=int(key[4:6]), day=int(key[6:]))
        try:
            val = float(raw)
        except (TypeError, ValueError):
            val = math.nan
        if math.isnan(val) or val == fill or val <= -998.0:
            val = math.nan
        dates.append(ts)
        data.append(val)

    if not dates:
        raise UpstreamError(f"NASA POWER returned an empty series for {variable_id}.")
    series = pd.Series(np.array(data, dtype=float), index=pd.DatetimeIndex(dates)).sort_index()
    return series[~series.index.duplicated(keep="last")]
