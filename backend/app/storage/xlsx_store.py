"""The ONLY module that reads or writes .xlsx files.

Design (see Architecture.md section 7):
- every write takes a FileLock, writes to a temp file, then os.replace()s it (atomic);
- callers in async code use the ``a*`` coroutine wrappers, which run the blocking
  openpyxl/pandas IO in a worker thread;
- the cache workbook is mirrored in memory so reads don't re-parse the file;
- daily series are cached in memory only (too many rows for a spreadsheet).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
from filelock import FileLock

log = logging.getLogger(__name__)

CATALOG_FILE = "catalog.xlsx"
CACHE_FILE = "cache.xlsx"
ANALYSES_FILE = "analyses.xlsx"

VARIABLE_COLUMNS = [
    "id", "name", "category", "units", "definition",
    "why_it_matters", "example_question", "source", "seasonal",
    "provider", "provider_id", "first_year", "scale", "offset",
]
DEMO_COLUMNS = ["demo_id", "title", "story", "request_json", "compare_request_json", "narration_steps_json"]
RESOURCE_COLUMNS = ["title", "provider", "kind", "url", "how_it_helps", "used_in_app"]
CATALOG_META_COLUMNS = ["key", "value"]
CACHE_META_COLUMNS = ["cache_key", "source", "variable_id", "lat", "lon", "resolution", "start_year", "end_year", "fetched_at", "n_rows"]
CACHE_SERIES_COLUMNS = ["cache_key", "date", "value"]
ANALYSIS_COLUMNS = [
    "analysis_id", "created_at", "variable_id", "region_json", "start_year", "end_year",
    "resolution", "deseasonalize", "alpha", "ols_slope_per_decade", "ols_p", "mk_p",
    "sens_slope_per_decade", "significant", "verdict", "request_json",
]
ANALYSIS_SERIES_COLUMNS = ["analysis_id", "date", "value", "anomaly"]


# --------------------------------------------------------------------------- low level

def _lock(path: Path) -> FileLock:
    return FileLock(str(path) + ".lock", timeout=10)


def read_workbook(path: Path) -> dict[str, pd.DataFrame]:
    """Read every sheet. Returns {} if the file does not exist.

    A corrupt file is renamed aside (``*.corrupt-<timestamp>.xlsx``) and {} is returned.
    """
    if not path.exists():
        return {}
    try:
        with _lock(path):
            return pd.read_excel(path, sheet_name=None, engine="openpyxl")
    except Exception:  # noqa: BLE001 - any parse failure means the file is unusable
        stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        aside = path.with_name(f"{path.stem}.corrupt-{stamp}.xlsx")
        log.exception("Unreadable workbook %s; moving it to %s", path.name, aside.name)
        try:
            os.replace(path, aside)
        except OSError:
            log.exception("Could not move corrupt workbook aside")
        return {}


def write_workbook(path: Path, sheets: dict[str, pd.DataFrame]) -> None:
    """Atomically replace ``path`` with a workbook containing ``sheets``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.stem + ".tmp.xlsx")
    with _lock(path):
        with pd.ExcelWriter(tmp, engine="openpyxl") as writer:
            for name, df in sheets.items():
                df.to_excel(writer, sheet_name=name, index=False)
        os.replace(tmp, path)


def _sheet(book: dict[str, pd.DataFrame], name: str, columns: list[str]) -> pd.DataFrame:
    df = book.get(name)
    if df is None:
        return pd.DataFrame(columns=columns)
    for col in columns:
        if col not in df.columns:
            df[col] = None
    return df[columns]


def _concat(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    if a.empty:
        return b.reset_index(drop=True)
    if b.empty:
        return a.reset_index(drop=True)
    return pd.concat([a, b], ignore_index=True)


# --------------------------------------------------------------------------- catalog

def _as_bool(v) -> bool:
    return str(v).strip().lower() in {"true", "1", "yes"}


def _as_float(v, default: float) -> float:
    try:
        f = float(v)
        return default if pd.isna(f) else f
    except (TypeError, ValueError):
        return default


def read_catalog_version(data_dir: Path) -> str | None:
    """The SEED_VERSION stored in catalog.xlsx (None if missing/old)."""
    meta = _sheet(read_workbook(data_dir / CATALOG_FILE), "meta", CATALOG_META_COLUMNS)
    match = meta[meta["key"].astype(str) == "seed_version"]
    return None if match.empty else str(match.iloc[-1]["value"]).strip()


def load_catalog(data_dir: Path) -> tuple[list[dict], list[dict], list[dict]]:
    """Return (variables, demos, resources) as plain dicts from catalog.xlsx."""
    book = read_workbook(data_dir / CATALOG_FILE)
    vars_df = _sheet(book, "variables", VARIABLE_COLUMNS)
    demos_df = _sheet(book, "demos", DEMO_COLUMNS)
    res_df = _sheet(book, "resources", RESOURCE_COLUMNS)

    variables: list[dict] = []
    for row in vars_df.to_dict(orient="records"):
        row = {k: ("" if pd.isna(v) else v) for k, v in row.items()}
        row["id"] = str(row["id"])
        row["seasonal"] = _as_bool(row["seasonal"])
        row["provider"] = str(row["provider"] or "power")
        row["provider_id"] = str(row["provider_id"] or row["id"])
        row["first_year"] = int(_as_float(row["first_year"], 1981))
        row["scale"] = _as_float(row["scale"], 1.0)
        row["offset"] = _as_float(row["offset"], 0.0)
        variables.append(row)

    resources = [
        {k: ("" if pd.isna(v) else v) for k, v in r.items()} | {"used_in_app": _as_bool(r["used_in_app"])}
        for r in res_df.to_dict(orient="records")
    ]

    demos: list[dict] = []
    for row in demos_df.to_dict(orient="records"):
        compare_raw = row.get("compare_request_json")
        demos.append(
            {
                "demo_id": str(row["demo_id"]),
                "title": str(row["title"]),
                "story": str(row["story"]),
                "request": json.loads(row["request_json"]),
                "compare_request": json.loads(compare_raw)
                if isinstance(compare_raw, str) and compare_raw.strip()
                else None,
                "narration_steps": json.loads(row["narration_steps_json"]),
            }
        )
    return variables, demos, resources


def write_catalog(
    data_dir: Path, variables: list[dict], demos: list[dict], resources: list[dict] | None = None,
    version: str = "",
) -> None:
    vars_df = pd.DataFrame(variables, columns=VARIABLE_COLUMNS)
    demo_rows = [
        {
            "demo_id": d["demo_id"],
            "title": d["title"],
            "story": d["story"],
            "request_json": json.dumps(d["request"]),
            "compare_request_json": json.dumps(d["compare_request"]) if d.get("compare_request") else "",
            "narration_steps_json": json.dumps(d["narration_steps"]),
        }
        for d in demos
    ]
    write_workbook(
        data_dir / CATALOG_FILE,
        {
            "variables": vars_df,
            "demos": pd.DataFrame(demo_rows, columns=DEMO_COLUMNS),
            "resources": pd.DataFrame(resources or [], columns=RESOURCE_COLUMNS),
            "meta": pd.DataFrame([{"key": "seed_version", "value": version}], columns=CATALOG_META_COLUMNS),
        },
    )


# --------------------------------------------------------------------------- store

class XlsxStore:
    """Cache + saved analyses. One instance per process (created in app lifespan)."""

    def __init__(self, data_dir: Path, ttl_days: int = 30) -> None:
        self.data_dir = data_dir
        self.ttl = timedelta(days=ttl_days)
        self._mem_lock = threading.Lock()
        self._cache_loaded = False
        self._cache_meta = pd.DataFrame(columns=CACHE_META_COLUMNS)
        self._cache_series: dict[str, pd.Series] = {}
        self._daily_mem: dict[str, pd.Series] = {}

    # ---- cache -----------------------------------------------------------
    @property
    def cache_path(self) -> Path:
        return self.data_dir / CACHE_FILE

    def _ensure_cache_loaded(self) -> None:
        if self._cache_loaded:
            return
        book = read_workbook(self.cache_path)
        meta = _sheet(book, "meta", CACHE_META_COLUMNS)
        series = _sheet(book, "series", CACHE_SERIES_COLUMNS)
        self._cache_meta = meta.reset_index(drop=True)
        self._cache_series = {}
        if not series.empty:
            series = series.copy()
            series["date"] = pd.to_datetime(series["date"])
            series["value"] = pd.to_numeric(series["value"], errors="coerce")
            for key, grp in series.groupby("cache_key"):
                s = pd.Series(grp["value"].to_numpy(dtype=float), index=pd.DatetimeIndex(grp["date"]))
                self._cache_series[str(key)] = s.sort_index()
        self._cache_loaded = True

    def get_cached(self, key: str, resolution: str) -> pd.Series | None:
        with self._mem_lock:
            if resolution == "daily":
                return self._daily_mem.get(key)
            self._ensure_cache_loaded()
            meta = self._cache_meta[self._cache_meta["cache_key"] == key]
            if meta.empty or key not in self._cache_series:
                return None
            fetched = pd.to_datetime(meta.iloc[-1]["fetched_at"], utc=True)
            if pd.isna(fetched) or datetime.now(UTC) - fetched.to_pydatetime() > self.ttl:
                return None
            return self._cache_series[key].copy()

    def put_cached_many(self, entries: list[tuple[dict, pd.Series]]) -> None:
        """Store several series. ``meta`` dicts need CACHE_META_COLUMNS minus fetched_at/n_rows."""
        if not entries:
            return
        with self._mem_lock:
            monthly = []
            for meta, series in entries:
                if meta["resolution"] == "daily":
                    self._daily_mem[meta["cache_key"]] = series.copy()
                    if len(self._daily_mem) > 200:  # crude bound on memory
                        self._daily_mem.pop(next(iter(self._daily_mem)))
                else:
                    monthly.append((meta, series))
            if not monthly:
                return
            self._ensure_cache_loaded()
            now = datetime.now(UTC).isoformat()
            keys = {m["cache_key"] for m, _ in monthly}
            meta_rows = [{**m, "fetched_at": now, "n_rows": int(len(s))} for m, s in monthly]
            for m, s in monthly:
                self._cache_series[m["cache_key"]] = s.copy()
            kept = self._cache_meta[~self._cache_meta["cache_key"].isin(keys)]
            self._cache_meta = _concat(kept, pd.DataFrame(meta_rows, columns=CACHE_META_COLUMNS))

            series_frames = [
                pd.DataFrame({"cache_key": k, "date": s.index.date, "value": s.to_numpy(dtype=float)})
                for k, s in self._cache_series.items()
            ]
            series_df = (
                pd.concat(series_frames, ignore_index=True)
                if series_frames
                else pd.DataFrame(columns=CACHE_SERIES_COLUMNS)
            )
            write_workbook(self.cache_path, {"meta": self._cache_meta, "series": series_df})

    # ---- analyses --------------------------------------------------------
    @property
    def analyses_path(self) -> Path:
        return self.data_dir / ANALYSES_FILE

    def save_analysis(self, row: dict, series: pd.DataFrame) -> None:
        with self._mem_lock:
            book = read_workbook(self.analyses_path)
            analyses = _sheet(book, "analyses", ANALYSIS_COLUMNS)
            series_sheet = _sheet(book, "series", ANALYSIS_SERIES_COLUMNS)
            analyses = _concat(analyses, pd.DataFrame([row], columns=ANALYSIS_COLUMNS))
            series_sheet = _concat(series_sheet, series[ANALYSIS_SERIES_COLUMNS])
            write_workbook(self.analyses_path, {"analyses": analyses, "series": series_sheet})

    def load_analysis_request(self, analysis_id: str) -> dict | None:
        """Return the stored AnalyzeRequest JSON for an analysis id, or None."""
        with self._mem_lock:
            book = read_workbook(self.analyses_path)
        analyses = _sheet(book, "analyses", ANALYSIS_COLUMNS)
        match = analyses[analyses["analysis_id"].astype(str) == analysis_id]
        if match.empty:
            return None
        return json.loads(match.iloc[-1]["request_json"])

    def storage_ok(self) -> bool:
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            probe = self.data_dir / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return True
        except OSError:
            return False

    # ---- async wrappers --------------------------------------------------
    async def aget_cached(self, key: str, resolution: str) -> pd.Series | None:
        return await asyncio.to_thread(self.get_cached, key, resolution)

    async def aput_cached_many(self, entries: list[tuple[dict, pd.Series]]) -> None:
        await asyncio.to_thread(self.put_cached_many, entries)

    async def asave_analysis(self, row: dict, series: pd.DataFrame) -> None:
        await asyncio.to_thread(self.save_analysis, row, series)

    async def aload_analysis_request(self, analysis_id: str) -> dict | None:
        return await asyncio.to_thread(self.load_analysis_request, analysis_id)
