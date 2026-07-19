import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.api.deps import get_db, verify_api_key
from vector_match.api.schemas import (
    CollectionCreateRequest,
    CollectionDeleteRequest,
    CollectionListResponse,
    CollectionResponse,
    CollectionUpdateRequest,
    IdResponse,
)
from vector_match.services.collections import CollectionService

router = APIRouter(prefix="/api/core/dataset/collection", dependencies=[Depends(verify_api_key)])


@router.post("/create", response_model=IdResponse)
async def create_collection(req: CollectionCreateRequest, session: AsyncSession = Depends(get_db)):
    col = await CollectionService(session).create(
        dataset_id=req.dataset_id, parent_id=req.parent_id, name=req.name, type=req.type
    )
    return IdResponse(id=col.id)


@router.get("/list", response_model=CollectionListResponse)
async def list_collections(
    dataset_id: uuid.UUID = Query(alias="datasetId"),
    parent_id: uuid.UUID | None = Query(default=None, alias="parentId"),
    offset: int = Query(default=0, ge=0),
    page_size: int = Query(default=10, ge=1, le=100, alias="pageSize"),
    search_text: str | None = Query(default=None, alias="searchText"),
    session: AsyncSession = Depends(get_db),
):
    items, total = await CollectionService(session).list_page(dataset_id, parent_id, offset, page_size, search_text)
    return CollectionListResponse(list=[CollectionResponse.model_validate(c) for c in items], total=total)


@router.get("/detail", response_model=CollectionResponse)
async def collection_detail(id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    return CollectionResponse.model_validate(await CollectionService(session).detail(id))


@router.put("/update", response_model=IdResponse)
async def update_collection(req: CollectionUpdateRequest, session: AsyncSession = Depends(get_db)):
    col = await CollectionService(session).update(req.id, name=req.name)
    return IdResponse(id=col.id)


@router.delete("/delete", response_model=IdResponse)
async def delete_collections(req: CollectionDeleteRequest, session: AsyncSession = Depends(get_db)):
    await CollectionService(session).delete(req.collection_ids)
    return IdResponse(id=req.collection_ids[0])
