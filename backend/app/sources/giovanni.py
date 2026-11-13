"""NASA Giovanni time-series adapter (GPM, OMI, AIRS, GLDAS, ...).

API: GET {base}/timeseries?data=<data id>&location=[lat,lon]&time=<start>/<end>
- point locations only (no area averages) -> regions are sampled point by point;
- needs a NASA Earthdata Login: either a Giovanni token obtained from {base}/signin
  (OAuth through urs.earthdata.nasa.gov using username + password), or an Earthdata
  user token sent as a Bearer header;
- the response is CSV text: metadata lines, then a header row starting with "Timestamp",
  then "<timestamp>,<value>" rows.

Credentials are never logged. Data IDs are listed in storage/seed.py.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import math
import time
from typing import Literal
from urllib.parse import urlparse

import httpx
import numpy as np
import pandas as pd

from ..errors import UpstreamError, UpstreamTimeout

log = logging.getLogger(__name__)

RETRY_STATUS = {429, 502, 503, 504}
EDL_HOST = "urs.earthdata.nasa.gov"
FILL_VALUES = {-9999.0, -9999.9, -999.0, -999.9, -1e30, 1e15, 9.9692099683868690e36}
AUTH_HELP = (
    "NASA Earthdata login was rejected by Giovanni. Check EARTHDATA_USERNAME/EARTHDATA_PASSWORD "
    "(or EARTHDATA_TOKEN) in .env, and log in once at https://giovanni.gsfc.nasa.gov/giovanni/ "
    "to approve the Giovanni application in your Earthdata profile."
)


class GiovanniSource:
    name = "giovanni"
    citation = (
        "Analyses and visualizations used in this study were produced with the Giovanni online data system, "
        "developed and maintained by the NASA GES DISC."
    )

    def __init__(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        token: str = "",
        username: str = "",
        password: str = "",
        max_concurrency: int = 2,
        retries: int = 2,
    ):
        self.client = client
        self.base_url = base_url.rstrip("/")
        self.edl_token = token.strip()
        self.username = username.strip()
        self.password = password
        self.sem = asyncio.Semaphore(max_concurrency)
        self.retries = retries
        self._giovanni_token: str | None = None
        self._token_expires: float = 0.0  # time.monotonic() deadline
        self._token_lock = asyncio.Lock()
        self.verified: bool | None = None  # set by verify(): None = not checked yet
        self.last_error: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.edl_token or (self.username and self.password))

    # ------------------------------------------------------------------ auth
    async def _signin(self) -> str:
        """Run Giovanni's /signin OAuth flow with Earthdata basic auth; returns the Giovanni token."""
        url = f"{self.base_url}/signin"
        auth = httpx.BasicAuth(self.username, self.password)
        for _ in range(8):  # follow redirects by hand: basic auth only for the Earthdata host
            host = urlparse(url).hostname or ""
            try:
                resp = await self.client.get(
                    url, auth=auth if host == EDL_HOST else None, follow_redirects=False, timeout=30
                )
            except httpx.TimeoutException as exc:
                raise UpstreamTimeout("Giovanni sign-in timed out.") from exc
            except httpx.HTTPError as exc:
                raise UpstreamError(f"Could not reach Giovanni sign-in: {exc.__class__.__name__}") from exc
            if resp.status_code in (301, 302, 303, 307, 308) and "location" in resp.headers:
                url = str(resp.url.join(resp.headers["location"]))
                continue
            host = urlparse(str(resp.url)).hostname or ""
            if resp.status_code == 200:
                token, ttl = parse_signin_token(resp.text)
                if token:
                    self._token_expires = time.monotonic() + max(ttl - 300, 60)
                    return token
                if host == EDL_HOST:
                    raise UpstreamError(
                        "Earthdata showed a login/approval page instead of signing in: check "
                        "EARTHDATA_USERNAME/EARTHDATA_PASSWORD, and approve the Giovanni app once at "
                        "https://giovanni.gsfc.nasa.gov/giovanni/ (sign in there)."
                    )
                raise UpstreamError(f"Giovanni sign-in returned no token (from {host}).")
            if resp.status_code == 401 and host == EDL_HOST:
                raise UpstreamError("Earthdata rejected EARTHDATA_USERNAME/EARTHDATA_PASSWORD (HTTP 401).")
            raise UpstreamError(f"Giovanni sign-in failed: HTTP {resp.status_code} from {host}.")
        raise UpstreamError("Giovanni sign-in failed: too many redirects.")

    async def _auth_headers(self, refresh: bool = False) -> dict[str, str]:
        if self.username and self.password:
            async with self._token_lock:
                if refresh or not self._giovanni_token or time.monotonic() >= self._token_expires:
                    self._giovanni_token = await self._signin()
            return {"authorizationtoken": self._giovanni_token}
        if self.edl_token:
            return {"Authorization": f"Bearer {self.edl_token}", "authorizationtoken": self.edl_token}
        raise UpstreamError(
            "Satellite variables need a free NASA Earthdata login. Add EARTHDATA_USERNAME and "
            "EARTHDATA_PASSWORD (or EARTHDATA_TOKEN) to .env and restart the backend."
        )

    # ------------------------------------------------------------------ data
    async def _get_csv(self, params: dict) -> str:
        url = f"{self.base_url}/timeseries"
        delay = 1.0
        refreshed = False
        attempt = 0
        while True:
            headers = await self._auth_headers()
            try:
                async with self.sem:
                    resp = await self.client.get(url, params=params, headers=headers, timeout=120)
            except httpx.TimeoutException as exc:
                if attempt >= self.retries:
                    raise UpstreamTimeout("NASA Giovanni did not respond in time.") from exc
            except httpx.HTTPError as exc:
                if attempt >= self.retries:
                    raise UpstreamError(f"Could not reach NASA Giovanni: {exc.__class__.__name__}") from exc
            else:
                if resp.status_code == 200:
                    return resp.text
                if resp.status_code in (401, 403) and "parameter is invalid" in resp.text:
                    # Giovanni answers 403 (body code 400) for an unknown data ID: not a login problem
                    raise UpstreamError(f"NASA Giovanni does not recognise the data ID '{params.get('data')}'.")
                if resp.status_code in (401, 403):
                    # a cached Giovanni token may have expired: sign in again once
                    if self.username and self.password and not refreshed:
                        refreshed = True
                        await self._auth_headers(refresh=True)
                        continue
                    raise UpstreamError(f"{AUTH_HELP} (Giovanni answered HTTP {resp.status_code}: {resp.text[:120]})")
                if resp.status_code not in RETRY_STATUS or attempt >= self.retries:
                    raise UpstreamError(f"NASA Giovanni returned HTTP {resp.status_code}: {resp.text[:200]}")
            attempt += 1
            log.warning("Giovanni attempt %d failed; retrying in %.1fs", attempt, delay)
            await asyncio.sleep(delay)
            delay *= 2

    async def fetch_point(
        self,
        variable_id: str,
        lat: float,
        lon: float,
        start_year: int,
        end_year: int,
        resolution: Literal["monthly", "daily"] = "monthly",
        *,
        provider_id: str = "",
        scale: float = 1.0,
        offset: float = 0.0,
    ) -> pd.Series:
        """Monthly series for one point (any native time step is averaged to months)."""
        params = {
            "data": provider_id or variable_id,
            "location": f"[{lat:.4f},{lon:.4f}]",
            "time": f"{start_year}-01-01T00:00:00/{end_year}-12-31T23:59:59",
        }
        text = await self._get_csv(params)
        series = parse_giovanni_csv(text)
        series = series * scale + offset
        return to_month_start(series)

    async def verify(self, probe_data_id: str) -> bool:
        """One small request (one year, one point) to check the login works; cached on self.verified."""
        if not self.configured:
            self.verified = False
            return False
        try:
            await self.fetch_point("probe", 40.0, -100.0, 2020, 2020, provider_id=probe_data_id)
            self.verified = True
            self.last_error = ""
        except (UpstreamError, UpstreamTimeout) as exc:
            log.warning("Giovanni check failed: %s", exc)
            self.last_error = str(exc)[:300]
            self.verified = False
        return self.verified


def parse_signin_token(text: str) -> tuple[str | None, float]:
    """Giovanni /gettoken answers JSON {"token": ..., "expires_in": s}; older docs show a bare string."""
    body = text.strip()
    ttl = 86400.0
    if body.startswith("{"):
        try:
            data = json.loads(body)
        except ValueError:
            return None, ttl
        token = str(data.get("token") or data.get("access_token") or "").strip()
        try:
            ttl = float(data.get("expires_in", ttl))
        except (TypeError, ValueError):
            pass
    else:
        token = body.strip('"')
    if not token or " " in token or "<" in token or "{" in token:
        return None, ttl
    return token, ttl


def parse_giovanni_csv(text: str) -> pd.Series:
    """Parse Giovanni time-series CSV (metadata lines, then 'Timestamp...,value' rows)."""
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.strip().lower().startswith("timestamp")), None)
    if start is None:
        raise UpstreamError("NASA Giovanni returned an unexpected response (no time-series table).")
    fill = None
    for ln in lines[:start]:
        key, _, val = ln.partition(",")
        if key.strip().lower() in ("fill_value", "fillvalue", "_fillvalue", "undef"):
            try:
                fill = float(val.strip())
            except ValueError:
                pass
    table = pd.read_csv(io.StringIO("\n".join(lines[start:])), header=0)
    if table.shape[1] < 2 or table.empty:
        raise UpstreamError("NASA Giovanni returned an empty time series.")
    ts = pd.to_datetime(table.iloc[:, 0].astype(str).str.strip(), errors="coerce", utc=True).dt.tz_localize(None)
    vals = pd.to_numeric(table.iloc[:, 1], errors="coerce").astype(float)
    bad = vals.isin(FILL_VALUES) | (vals.abs() > 1e20)
    if fill is not None:
        bad |= np.isclose(vals, fill)
    vals = vals.mask(bad)
    series = pd.Series(vals.to_numpy(), index=pd.DatetimeIndex(ts)).dropna(how="all")
    series = series[series.index.notna()].sort_index()
    if series.empty:
        raise UpstreamError("NASA Giovanni returned no usable values for this place and period.")
    return series


def to_month_start(series: pd.Series) -> pd.Series:
    """Average any time step (3-hourly, daily, monthly) to calendar months indexed by month start."""
    monthly = series.groupby(series.index.to_period("M")).mean()
    monthly.index = monthly.index.to_timestamp(how="start")
    return monthly.astype(float).where(lambda s: ~s.isin([math.inf, -math.inf]))
