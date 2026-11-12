import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

POWER_URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"
WEATHER_BASE = "https://api.weatherapi.com/v1"


def power_payload(param: str, start: int, end: int, slope_per_year: float = 0.05, seed: int = 0,
                  base: float = 0.0, amp: float = 10.0, fill_months: tuple[str, ...] = ()) -> dict:
    """Synthetic NASA POWER monthly payload incl. the month-13 annual mean."""
    rng = np.random.default_rng(seed)
    values: dict[str, float] = {}
    for y in range(start, end + 1):
        months = []
        for m in range(1, 13):
            t = (y - start) + (m - 0.5) / 12
            v = base + slope_per_year * t + amp * np.sin(2 * np.pi * (m - 1) / 12) + rng.normal(0, 0.5)
            key = f"{y}{m:02d}"
            values[key] = -999.0 if key in fill_months else round(float(v), 2)
            months.append(v)
        values[f"{y}13"] = round(float(np.mean(months)), 2)
    return {
        "header": {"fill_value": -999.0},
        "parameters": {param: {"units": "C"}},
        "properties": {"parameter": {param: values}},
    }


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(data_dir=str(tmp_path / "data"), weatherapi_key="test-key", cache_ttl_days=30)


@pytest.fixture
def app(settings):
    return create_app(settings)
