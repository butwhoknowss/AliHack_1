"""WeatherAPI.com adapter: place search (geocoding) and current conditions.

NOT used for trends: its history only reaches back a short time.
The API key is a query parameter, so never log request URLs from this module.
"""

from __future__ import annotations

import httpx

from ..errors import NotFoundError, UpstreamError, UpstreamTimeout


class WeatherApiSource:
    name = "weatherapi"

    def __init__(self, client: httpx.AsyncClient, base_url: str, api_key: str):
        self.client = client
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def _get(self, endpoint: str, q: str) -> dict | list:
        if not self.configured:
            raise UpstreamError("Weather service is not configured (WEATHERAPI_KEY missing).")
        try:
            resp = await self.client.get(
                f"{self.base_url}/{endpoint}", params={"key": self.api_key, "q": q}, timeout=15
            )
        except httpx.TimeoutException as exc:
            raise UpstreamTimeout("Weather service did not respond in time.") from exc
        except httpx.HTTPError as exc:
            raise UpstreamError(f"Could not reach the weather service: {exc.__class__.__name__}") from exc

        if resp.status_code in (401, 403):
            raise UpstreamError("Weather service key is invalid or disabled.")
        if resp.status_code == 400:
            # WeatherAPI uses 400 + error code 1006 for "No location found"
            try:
                code = resp.json().get("error", {}).get("code")
            except ValueError:
                code = None
            if code == 1006:
                raise NotFoundError("No matching location found.")
            raise UpstreamError("Weather service rejected the request.")
        if resp.status_code != 200:
            raise UpstreamError(f"Weather service returned HTTP {resp.status_code}.")
        try:
            return resp.json()
        except ValueError as exc:
            raise UpstreamError("Weather service returned invalid JSON.") from exc

    async def search(self, text: str) -> list[dict]:
        data = await self._get("search.json", text)
        if not isinstance(data, list):
            raise UpstreamError("Unexpected search response from weather service.")
        return [
            {
                "name": str(d.get("name", "")),
                "region": str(d.get("region", "")),
                "country": str(d.get("country", "")),
                "lat": float(d["lat"]),
                "lon": float(d["lon"]),
            }
            for d in data
            if "lat" in d and "lon" in d
        ]

    async def reverse(self, lat: float, lon: float) -> dict | None:
        """Nearest named place to a coordinate (WeatherAPI search accepts "lat,lon"); None if none."""
        results = await self.search(f"{lat:.4f},{lon:.4f}")
        return results[0] if results else None

    async def current(self, lat: float, lon: float) -> dict:
        data = await self._get("current.json", f"{lat:.4f},{lon:.4f}")
        try:
            loc, cur = data["location"], data["current"]
            icon = str(cur["condition"].get("icon", ""))
            if icon.startswith("//"):
                icon = "https:" + icon
            return {
                "location": str(loc.get("name", "")),
                "country": str(loc.get("country", "")),
                "local_time": str(loc.get("localtime", "")),
                "temp_c": float(cur["temp_c"]),
                "feelslike_c": float(cur["feelslike_c"]),
                "humidity": int(cur["humidity"]),
                "wind_kph": float(cur["wind_kph"]),
                "precip_mm": float(cur.get("precip_mm", 0.0)),
                "condition": str(cur["condition"].get("text", "")),
                "icon": icon,
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise UpstreamError("Unexpected current-weather response from weather service.") from exc

    async def ping(self) -> bool:
        if not self.configured:
            return False
        try:
            await self._get("current.json", "London")
            return True
        except (UpstreamError, UpstreamTimeout, NotFoundError):
            return False
