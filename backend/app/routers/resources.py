from fastapi import APIRouter, Depends

from ..deps import get_resources
from ..models import Resource

router = APIRouter(tags=["resources"])


@router.get("/resources", response_model=list[Resource])
async def list_resources(resources: list[dict] = Depends(get_resources)) -> list[Resource]:
    """Official challenge resources (NASA, NOAA, KNMI, CSA) and how each relates to this tool."""
    return [Resource(**r) for r in resources]
