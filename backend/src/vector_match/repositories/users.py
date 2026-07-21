import uuid

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.core.exceptions import ConflictError
from vector_match.db.models import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        username: str,
        email: str | None,
        password_hash: str,
        is_superuser: bool = False,
        is_active: bool = True,
    ) -> User:
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            is_superuser=is_superuser,
            is_active=is_active,
        )
        self.session.add(user)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("username or email already exists") from exc
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        stmt = select(User).where(User.id == user_id, User.isvalid == 1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username, User.isvalid == 1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def exists_username(self, username: str) -> bool:
        stmt = select(User.id).where(User.username == username, User.isvalid == 1)
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    async def exists_email(self, email: str) -> bool:
        stmt = select(User.id).where(User.email == email, User.isvalid == 1)
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    async def list_page(self, offset: int, page_size: int) -> tuple[list[User], int]:
        stmt_total = select(func.count()).select_from(User).where(User.isvalid == 1)
        total = await self.session.scalar(stmt_total)
        stmt = (
            select(User)
            .where(User.isvalid == 1)
            .order_by(User.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list((await self.session.execute(stmt)).scalars().all()), int(total or 0)

    async def update_fields(self, user: User, is_active: bool | None = None, is_superuser: bool | None = None) -> None:
        if is_active is not None:
            user.is_active = is_active
        if is_superuser is not None:
            user.is_superuser = is_superuser
        await self.session.flush()

    async def soft_delete(self, user: User) -> None:
        stmt = update(User).where(User.id == user.id).values(isvalid=0)
        await self.session.execute(stmt)
