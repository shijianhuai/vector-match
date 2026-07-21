import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.api.deps import get_current_user, get_db, require_superuser
from vector_match.api.schemas import UserListResponse, UserResponse, UserUpdateRequest
from vector_match.db.models import User
from vector_match.services.users import UserService

router = APIRouter(prefix="/api/users", dependencies=[Depends(require_superuser)])


@router.get("/", response_model=UserListResponse)
async def list_users(
    offset: int = Query(default=0, ge=0),
    page_size: int = Query(default=10, ge=1, le=100, alias="pageSize"),
    session: AsyncSession = Depends(get_db),
):
    items, total = await UserService(session).list_users(offset, page_size)
    return UserListResponse(list=[UserResponse.model_validate(u) for u in items], total=total)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    req: UserUpdateRequest,
    session: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    user = await UserService(session).update_user(
        actor=actor, user_id=user_id, is_active=req.is_active, is_superuser=req.is_superuser
    )
    return UserResponse.model_validate(user)
