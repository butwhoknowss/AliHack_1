from fastapi import APIRouter, Depends, Query

from ..deps import get_variables
from ..models import Variable
from ..services.analysis import get_variable

router = APIRouter(tags=["variables"])


@router.get("/variables", response_model=list[Variable])
async def list_variables(
    category: str | None = Query(None, max_length=40),
    q: str | None = Query(None, max_length=80),
    variables: dict[str, dict] = Depends(get_variables),
) -> list[Variable]:
    out = []
    needle = (q or "").strip().lower()
    for row in variables.values():
        if category and row["category"].lower() != category.lower():
            continue
        if needle and needle not in f"{row['id']} {row['name']} {row['definition']}".lower():
            continue
        out.append(Variable(**row))
    return out


@router.get("/variables/{variable_id}", response_model=Variable)
async def one_variable(variable_id: str, variables: dict[str, dict] = Depends(get_variables)) -> Variable:
    return get_variable(variables, variable_id)
