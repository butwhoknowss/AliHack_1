from fastapi import APIRouter, Depends

from ..deps import get_resources
from ..models import Resource, ResourceStep
from ..storage.seed import RESOURCE_STEPS

router = APIRouter(tags=["resources"])


@router.get("/resources", response_model=list[Resource])
async def list_resources(resources: list[dict] = Depends(get_resources)) -> list[Resource]:
    """Official challenge resources (NASA, NOAA, KNMI, CSA): how each relates to this tool and to each other."""
    return [Resource(**r) for r in resources]


@router.get("/resources/steps", response_model=list[ResourceStep])
async def list_resource_steps() -> list[ResourceStep]:
    """The detective workflow the resources are grouped by: data -> test -> check -> explain."""
    return [ResourceStep(**s) for s in RESOURCE_STEPS]
