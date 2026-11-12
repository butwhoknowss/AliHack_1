from fastapi import APIRouter, Depends

from ..deps import get_demos
from ..models import Demo

router = APIRouter(tags=["demos"])


@router.get("/demos", response_model=list[Demo])
async def list_demos(demos: list[dict] = Depends(get_demos)) -> list[Demo]:
    return [Demo(**d) for d in demos]
