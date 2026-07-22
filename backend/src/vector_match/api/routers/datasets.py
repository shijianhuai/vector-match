import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.api.deps import (
    get_current_user,
    get_db,
    require_dataset_access,
)
from vector_match.api.schemas import (
    DatasetCreateRequest,
    DatasetMemberCreateRequest,
    DatasetMemberResponse,
    DatasetMemberUpdateRequest,
    DatasetResponse,
    DatasetUpdateRequest,
    IdResponse,
)
from vector_match.core.config import Settings, get_settings
from vector_match.db.models import User
from vector_match.services.datasets import DatasetService
from vector_match.services.members import MemberService

router = APIRouter(prefix="/api/core/dataset", dependencies=[Depends(get_current_user)])


@router.post("/create", response_model=IdResponse)
async def create_dataset(
    req: DatasetCreateRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    ds = await DatasetService(session).create(
        user=user,
        name=req.name,
        description=req.description,
        vector_model=settings.embedding_model,
    )
    return IdResponse(id=ds.id)


@router.get("/list", response_model=list[DatasetResponse])
async def list_datasets(
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = await DatasetService(session).list(user=user)
    return [
        DatasetResponse(
            id=ds.id, name=ds.name, description=ds.description, vector_model=ds.vector_model, my_role=role
        )
        for ds, role in items
    ]


@router.get("/detail", dependencies=[Depends(require_dataset_access("viewer"))], response_model=DatasetResponse)
async def dataset_detail(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ds, role = await DatasetService(session).detail(id, user=user)
    return DatasetResponse(
        id=ds.id, name=ds.name, description=ds.description, vector_model=ds.vector_model, my_role=role
    )


@router.put("/update", dependencies=[Depends(require_dataset_access("editor"))], response_model=IdResponse)
async def update_dataset(
    req: DatasetUpdateRequest,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ds = await DatasetService(session).update(req.id, name=req.name, description=req.description, operator_id=user.id)
    return IdResponse(id=ds.id)


@router.delete("/delete", dependencies=[Depends(require_dataset_access("owner"))], response_model=IdResponse)
async def delete_dataset(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await DatasetService(session).delete(id, operator_id=user.id)
    return IdResponse(id=id)


@router.get("/{dataset_id}/members", dependencies=[Depends(require_dataset_access("viewer"))], response_model=list[DatasetMemberResponse])
async def list_members(
    dataset_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    rows = await MemberService(session).list_members(dataset_id)
    return [
        DatasetMemberResponse(
            id=member.id,
            dataset_id=member.dataset_id,
            user_id=user.id,
            username=user.username,
            role=member.role,
        )
        for member, user in rows
    ]


@router.post("/{dataset_id}/members", dependencies=[Depends(require_dataset_access("owner"))], response_model=IdResponse)
async def add_member(
    dataset_id: uuid.UUID,
    req: DatasetMemberCreateRequest,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    member = await MemberService(session).add_member(dataset_id, req.username, req.role, operator_id=user.id)
    return IdResponse(id=member.id)


@router.patch(
    "/{dataset_id}/members/{user_id}", dependencies=[Depends(require_dataset_access("owner"))], response_model=IdResponse
)
async def update_member(
    dataset_id: uuid.UUID,
    user_id: int,
    req: DatasetMemberUpdateRequest,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    member = await MemberService(session).update_role(dataset_id, user_id, req.role, operator_id=user.id)
    return IdResponse(id=member.id)


@router.delete(
    "/{dataset_id}/members/{user_id}", dependencies=[Depends(require_dataset_access("owner"))], response_model=IdResponse
)
async def remove_member(
    dataset_id: uuid.UUID,
    user_id: int,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await MemberService(session).remove_member(dataset_id, user_id, operator_id=user.id)
    return IdResponse(id=user_id)
