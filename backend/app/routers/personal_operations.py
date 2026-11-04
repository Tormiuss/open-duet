from fastapi import APIRouter, Depends, HTTPException, Query
from app.services.local_access_policy import require_local_access
from app.services import personal_operations as operations

router = APIRouter(prefix="/personal-operations", tags=["Personal operations"], dependencies=[Depends(require_local_access)])


@router.get("")
async def overview():
    return await operations.overview()


@router.get("/search")
async def search(query: str = Query(min_length=1, max_length=200)):
    try:
        return await operations.read_tool("atlas_search", {"query": query})
    except Exception:
        raise HTTPException(503, "Personal Atlas is unavailable; search coverage is unknown") from None


@router.get("/entry/{identifier}")
async def entry(identifier: str):
    try:
        return await operations.read_tool("atlas_get", {"id": identifier})
    except Exception:
        raise HTTPException(503, "Personal Atlas entry is unavailable") from None
