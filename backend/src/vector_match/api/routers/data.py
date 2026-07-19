import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.api.deps import get_db, verify_api_key
from vector_match.api.schemas import (
    DataDetailResponse,
    DataItemResponse,
    DataListResponse,
    DataUpdateRequest,
    IdResponse,
    IndexResponse,
    PushDataRequest,
    PushDataResponse,
)
from vector_match.services.data import DataService, PushItem

router = APIRouter(prefix="/api/core/dataset/data", dependencies=[Depends(verify_api_key)])


@router.post("/pushData", response_model=PushDataResponse)
async def push_data(req: PushDataRequest, session: AsyncSession = Depends(get_db)):
    items = [PushItem(q=item.q, a=item.a, indexes=[idx.text for idx in item.indexes]) for item in req.data]
    n = await DataService(session).push(req.collection_id, items)
    return PushDataResponse(insert_len=n)


@router.get("/list", response_model=DataListResponse)
async def list_data(
    collection_id: uuid.UUID = Query(alias="collectionId"),
    offset: int = Query(default=0, ge=0),
    page_size: int = Query(default=10, ge=1, le=100, alias="pageSize"),
    search_text: str | None = Query(default=None, alias="searchText"),
    session: AsyncSession = Depends(get_db),
):
    items, total, trained = await DataService(session).list_page(collection_id, offset, page_size, search_text)
    return DataListResponse(
        list=[
            DataItemResponse(
                id=d.id,
                dataset_id=d.dataset_id,
                collection_id=d.collection_id,
                q=d.q,
                a=d.a,
                trained=d.id in trained,
            )
            for d in items
        ],
        total=total,
    )


@router.get("/detail", response_model=DataDetailResponse)
async def data_detail(id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    data, indexes, trained = await DataService(session).detail(id)
    return DataDetailResponse(
        id=data.id,
        dataset_id=data.dataset_id,
        collection_id=data.collection_id,
        q=data.q,
        a=data.a,
        trained=trained,
        indexes=[IndexResponse(type=i.type, text=i.text) for i in indexes],
    )


@router.put("/update", response_model=IdResponse)
async def update_data(req: DataUpdateRequest, session: AsyncSession = Depends(get_db)):
    indexes = [idx.text for idx in req.indexes] if req.indexes is not None else None
    await DataService(session).update(req.data_id, q=req.q, a=req.a, indexes=indexes)
    return IdResponse(id=req.data_id)


@router.delete("/delete", response_model=IdResponse)
async def delete_data(id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    await DataService(session).delete(id)
    return IdResponse(id=id)
