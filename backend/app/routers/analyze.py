from fastapi import APIRouter, Depends, Path

from ..deps import get_power, get_store, get_variables
from ..errors import NotFoundError
from ..models import AnalyzeRequest, AnalyzeResponse
from ..services.analysis import run_analysis
from ..sources.nasa_power import NasaPowerSource
from ..storage.xlsx_store import XlsxStore

router = APIRouter(tags=["analysis"])

ID_PATTERN = r"^[0-9a-f]{32}$"


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    req: AnalyzeRequest,
    variables: dict[str, dict] = Depends(get_variables),
    power: NasaPowerSource = Depends(get_power),
    store: XlsxStore = Depends(get_store),
) -> AnalyzeResponse:
    return await run_analysis(req, variables=variables, source=power, store=store)


async def reload_analysis(
    analysis_id: str, variables: dict[str, dict], power: NasaPowerSource, store: XlsxStore
) -> AnalyzeResponse:
    """Re-create a saved analysis from its stored request (series come from the cache)."""
    stored = await store.aload_analysis_request(analysis_id)
    if stored is None:
        raise NotFoundError(f"No saved analysis with id '{analysis_id}'.")
    req = AnalyzeRequest(**{**stored, "save": False})
    return await run_analysis(req, variables=variables, source=power, store=store, analysis_id=analysis_id)


@router.get("/analyses/{analysis_id}", response_model=AnalyzeResponse)
async def get_analysis(
    analysis_id: str = Path(..., pattern=ID_PATTERN),
    variables: dict[str, dict] = Depends(get_variables),
    power: NasaPowerSource = Depends(get_power),
    store: XlsxStore = Depends(get_store),
) -> AnalyzeResponse:
    return await reload_analysis(analysis_id, variables, power, store)
