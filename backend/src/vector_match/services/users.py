import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.core.config import Settings
from vector_match.core.exceptions import ConflictError
from vector_match.core.security import hash_password, verify_password
from vector_match.db.models import Dataset, User
from vector_match.repositories.members import DatasetMemberRepository
from vector_match.repositories.users import UserRepository

_DUMMY_HASH: str | None = None


def _dummy_hash() -> str:
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password("dummy")
    return _DUMMY_HASH


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.users = UserRepository(session)
        self.members = DatasetMemberRepository(session)

    async def create_user(
        self,
        username: str,
        password: str,
        email: str | None = None,
        is_superuser: bool = False,
    ) -> User:
        username = username.lower().strip()
        if email is not None:
            email = email.lower().strip()
        if await self.users.exists_username(username):
            raise HTTPException(status_code=409, detail="username already exists")
        if email and await self.users.exists_email(email):
            raise HTTPException(status_code=409, detail="email already exists")
        if len(password) < 6:
            raise HTTPException(status_code=422, detail="password too short")
        try:
            user = await self.users.create(
                username=username,
                email=email,
                password_hash=hash_password(password),
                is_superuser=is_superuser,
            )
            await self.session.commit()
        except ConflictError as exc:
            raise HTTPException(status_code=409, detail="username or email already exists") from exc
        return user

    async def authenticate(self, username: str, password: str) -> User:
        username = username.lower().strip()
        user = await self.users.get_by_username(username)
        if user is None:
            # 用户不存在时也执行一次 argon2 verify, 避免通过时序差异枚举用户
            verify_password(password, _dummy_hash())
            raise HTTPException(status_code=401, detail="invalid credentials")
        if not user.is_active or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="invalid credentials")
        return user

    async def get_by_id(self, user_id) -> User | None:
        return await self.users.get_by_id(user_id)

    async def list_users(self, offset: int, page_size: int) -> tuple[list[User], int]:
        return await self.users.list_page(offset, page_size)

    async def update_user(
        self, actor: User, user_id: uuid.UUID, is_active: bool | None = None, is_superuser: bool | None = None
    ) -> User:
        if actor.id == user_id:
            raise HTTPException(status_code=422, detail="cannot modify yourself")
        user = await self.users.get_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="user not found")
        await self.users.update_fields(user, is_active=is_active, is_superuser=is_superuser)
        await self.session.commit()
        return user

    async def seed_admin(self, settings: Settings) -> None:
        if not settings.admin_username or not settings.admin_password:
            return
        username = settings.admin_username.lower().strip()
        if await self.users.exists_username(username):
            return
        admin = await self.users.create(
            username=username,
            email=None,
            password_hash=hash_password(settings.admin_password),
            is_superuser=True,
            is_active=True,
        )
        await self.session.commit()
        await self.backfill_owners(admin.id)

    async def backfill_owners(self, admin_user_id: uuid.UUID) -> None:
        stmt = select(Dataset).where(Dataset.isvalid == 1)
        datasets = list((await self.session.execute(stmt)).scalars().all())
        for ds in datasets:
            has_owner = await self.members.count_valid_owners(ds.id) > 0
            if not has_owner:
                await self.members.get_or_create(ds.id, admin_user_id, "owner")
        await self.session.commit()

