import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.api.deps import get_db, verify_api_key
from vector_match.api.schemas import (
    DatasetCreateRequest,
    DatasetResponse,
    DatasetUpdateRequest,
    IdResponse,
)
from vector_match.core.config import Settings, get_settings
from vector_match.services.datasets import DatasetService

router = APIRouter(prefix="/api/core/dataset", dependencies=[Depends(verify_api_key)])


@router.post("/create", response_model=IdResponse)
async def create_dataset(
    req: DatasetCreateRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    ds = await DatasetService(session).create(
        name=req.name, description=req.description, vector_model=settings.embedding_model
    )
    return IdResponse(id=ds.id)


@router.get("/list", response_model=list[DatasetResponse])
async def list_datasets(session: AsyncSession = Depends(get_db)):
    items = await DatasetService(session).list()
    return [DatasetResponse.model_validate(d) for d in items]


@router.get("/detail", response_model=DatasetResponse)
async def dataset_detail(id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    return DatasetResponse.model_validate(await DatasetService(session).detail(id))


@router.put("/update", response_model=IdResponse)
async def update_dataset(req: DatasetUpdateRequest, session: AsyncSession = Depends(get_db)):
    ds = await DatasetService(session).update(req.id, name=req.name, description=req.description)
    return IdResponse(id=ds.id)


@router.delete("/delete", response_model=IdResponse)
async def delete_dataset(id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    await DatasetService(session).delete(id)
    return IdResponse(id=id)
