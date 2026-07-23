from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.api.deps import get_current_user, get_db, require_role
from vector_match.api.schemas import UserListResponse, UserResponse, UserSearchItem, UserUpdateRequest
from vector_match.db.models import User
from vector_match.services.users import UserService

router = APIRouter(prefix="/api/users")


@router.get("/", response_model=UserListResponse, dependencies=[Depends(require_role("superadmin"))])
async def list_users(
    offset: int = Query(default=0, ge=0),
    page_size: int = Query(default=10, ge=1, le=100, alias="pageSize"),
    is_approved: bool | None = Query(default=None, alias="isApproved"),
    session: AsyncSession = Depends(get_db),
):
    items, total = await UserService(session).list_users(offset, page_size, is_approved=is_approved)
    return UserListResponse(list=[UserResponse.model_validate(u) for u in items], total=total)


@router.get("/search", response_model=list[UserSearchItem], dependencies=[Depends(require_role("admin"))])
async def search_users(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=10, ge=1, le=20),
    session: AsyncSession = Depends(get_db),
):
    items = await UserService(session).search_users(q, limit)
    return [UserSearchItem.model_validate(u) for u in items]


@router.patch("/{user_id}", response_model=UserResponse, dependencies=[Depends(require_role("superadmin"))])
async def update_user(
    user_id: int,
    req: UserUpdateRequest,
    session: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    user = await UserService(session).update_user(
        actor=actor,
        user_id=user_id,
        role=req.role,
        is_approved=req.is_approved,
        is_active=req.is_active,
    )
    return UserResponse.model_validate(user)
