from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.api.deps import get_current_user, get_db, require_api_key_permission
from vector_match.api.schemas import (
    ApiKeyCreateRequest,
    ApiKeyListResponse,
    ApiKeyResponse,
    ApiKeyUpdateRequest,
    IdResponse,
)
from vector_match.db.models import User
from vector_match.services.api_keys import ApiKeyService

router = APIRouter(prefix="/api/api-keys", dependencies=[Depends(require_api_key_permission)])


@router.get("/", response_model=ApiKeyListResponse)
async def list_api_keys(
    offset: int = Query(default=0, ge=0),
    page_size: int = Query(default=10, ge=1, le=100, alias="pageSize"),
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = await ApiKeyService(session).list_keys(user, offset, page_size)
    return ApiKeyListResponse(list=[ApiKeyResponse.model_validate(k) for k in items], total=total)


@router.post("/", response_model=ApiKeyResponse)
async def create_api_key(
    req: ApiKeyCreateRequest,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    key = await ApiKeyService(session).create_key(user, req.name)
    return ApiKeyResponse.model_validate(key)


@router.patch("/{key_id}", response_model=ApiKeyResponse)
async def update_api_key(
    key_id: int,
    req: ApiKeyUpdateRequest,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    key = await ApiKeyService(session).update_key(user, key_id, req.name)
    return ApiKeyResponse.model_validate(key)


@router.delete("/{key_id}", response_model=IdResponse)
async def delete_api_key(
    key_id: int,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await ApiKeyService(session).delete_key(user, key_id)
    return IdResponse(id=key_id)
