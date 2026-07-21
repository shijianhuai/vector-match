from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.api.deps import get_current_user, get_db
from vector_match.api.schemas import IdResponse, LoginRequest, LoginResponse, RegisterRequest, UserResponse
from vector_match.core.config import Settings, get_settings
from vector_match.core.security import create_access_token
from vector_match.db.models import User
from vector_match.services.users import UserService

router = APIRouter(prefix="/api/auth")


@router.post("/register", response_model=IdResponse)
async def register(req: RegisterRequest, session: AsyncSession = Depends(get_db)):
    user = await UserService(session).create_user(
        username=req.username, password=req.password, email=req.email
    )
    return IdResponse(id=user.id)


@router.post("/login", response_model=LoginResponse)
async def login(
    req: LoginRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    user = await UserService(session).authenticate(req.username, req.password)
    token = create_access_token(str(user.id), settings)
    return LoginResponse(token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user)
