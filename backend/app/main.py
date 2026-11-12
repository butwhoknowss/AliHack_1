"""FastAPI application entry point.

Run (from the backend/ folder):  uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import REPO_ROOT, Settings, get_settings
from .errors import DataQualityError, NotFoundError, UpstreamError, UpstreamTimeout
from .routers import ALL_ROUTERS
from .sources.nasa_power import NasaPowerSource
from .sources.weatherapi import WeatherApiSource
from .storage.seed import ensure_catalog
from .storage.xlsx_store import XlsxStore, load_catalog

log = logging.getLogger("app")


def _configure_logging(level: str) -> None:
    logging.basicConfig(level=level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # httpx logs full URLs at INFO, which would leak the WeatherAPI key -> silence it.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    _configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        data_dir = settings.data_path
        data_dir.mkdir(parents=True, exist_ok=True)
        if ensure_catalog(data_dir):
            log.info("Created %s", data_dir / "catalog.xlsx")
        variables, demos = load_catalog(data_dir)
        app.state.variables = {v["id"]: v for v in variables}
        app.state.demos = demos
        app.state.store = XlsxStore(data_dir, settings.cache_ttl_days)

        client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.http_timeout_seconds, connect=15.0),
            headers={"User-Agent": "EarthTrendDetective/1.0 (educational hackathon project)"},
            follow_redirects=True,
        )
        app.state.http = client
        app.state.power = NasaPowerSource(client, settings.nasa_power_base_url)
        app.state.weather = WeatherApiSource(client, settings.weatherapi_base_url, settings.weatherapi_key)
        if not settings.weatherapi_key:
            log.warning("WEATHERAPI_KEY is not set: place search and current weather are disabled.")
        log.info("Loaded %d variables and %d demos", len(variables), len(demos))
        try:
            yield
        finally:
            await client.aclose()

    app = FastAPI(
        title="Earth Trend Detective API",
        version="1.0.0",
        description="Find, visualize and test trends in NASA Earth science data.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
        expose_headers=["Content-Disposition"],
    )

    @app.middleware("http")
    async def access_log(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        # path only — never the query string (could contain secrets)
        log.info("%s %s %d %.0fms", request.method, request.url.path, response.status_code,
                 (time.perf_counter() - start) * 1000)
        return response

    def _err(status: int, msg: str) -> JSONResponse:
        return JSONResponse(status_code=status, content={"detail": msg})

    @app.exception_handler(NotFoundError)
    async def _not_found(_: Request, exc: NotFoundError):
        return _err(404, str(exc))

    @app.exception_handler(DataQualityError)
    async def _bad_data(_: Request, exc: DataQualityError):
        return _err(422, str(exc))

    @app.exception_handler(UpstreamError)
    async def _upstream(_: Request, exc: UpstreamError):
        return _err(502, str(exc))

    @app.exception_handler(UpstreamTimeout)
    async def _timeout(_: Request, exc: UpstreamTimeout):
        return _err(504, str(exc))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        msgs = []
        for e in exc.errors():
            msg = str(e.get("msg", "Invalid value")).removeprefix("Value error, ")
            loc = ".".join(str(p) for p in e.get("loc", []) if p not in ("body", "query", "path"))
            msgs.append(f"{loc}: {msg}" if loc else msg)
        return JSONResponse(status_code=422, content={"detail": "; ".join(msgs) or "Invalid request."})

    for router in ALL_ROUTERS:
        app.include_router(router, prefix="/api")

    # Convenience: also serve the dashboard at http://127.0.0.1:8000/ (Live Server is the main way).
    frontend_dir = REPO_ROOT / "frontend"
    if frontend_dir.is_dir():
        app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

    return app


app = create_app()
