"""Application settings, loaded from environment variables and the repo-root .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    weatherapi_key: str = ""
    nasa_power_base_url: str = "https://power.larc.nasa.gov/api"
    weatherapi_base_url: str = "https://api.weatherapi.com/v1"
    data_dir: str = "./data"
    cache_ttl_days: int = 30
    http_timeout_seconds: float = 60.0
    log_level: str = "INFO"
    # Comma-separated extra origins allowed by CORS (e.g. a Netlify URL).
    cors_origins: str = ""

    @property
    def data_path(self) -> Path:
        """DATA_DIR resolved against the repo root when relative."""
        p = Path(self.data_dir)
        return p if p.is_absolute() else (REPO_ROOT / p).resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        defaults = [
            "http://127.0.0.1:5500",
            "http://localhost:5500",
            "http://127.0.0.1:5501",
            "http://localhost:5501",
        ]
        extra = [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]
        return defaults + extra


@lru_cache
def get_settings() -> Settings:
    return Settings()
