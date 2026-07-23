from sqlalchemy import func, select
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
        role: str = "user",
        is_approved: bool = False,
        is_active: bool = True,
        creator_id: int | None = None,
        updater_id: int | None = None,
    ) -> User:
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            role=role,
            is_approved=is_approved,
            is_active=is_active,
            creator_id=creator_id,
            updater_id=updater_id,
        )
        self.session.add(user)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("username or email already exists") from exc
        return user

    async def get_by_id(self, user_id: int) -> User | None:
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

    async def list_page(self, offset: int, page_size: int, is_approved: bool | None = None) -> tuple[list[User], int]:
        conditions = [User.isvalid == 1]
        if is_approved is not None:
            conditions.append(User.is_approved == is_approved)
        stmt_total = select(func.count()).select_from(User).where(*conditions)
        total = await self.session.scalar(stmt_total)
        stmt = (
            select(User)
            .where(*conditions)
            .order_by(User.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list((await self.session.execute(stmt)).scalars().all()), int(total or 0)

    async def count_active_superadmins(self, exclude_user_id: int | None = None) -> int:
        conditions = [User.isvalid == 1, User.role == "superadmin", User.is_active, User.is_approved]
        if exclude_user_id is not None:
            conditions.append(User.id != exclude_user_id)
        total = await self.session.scalar(select(func.count()).select_from(User).where(*conditions))
        return int(total or 0)

    async def search_valid(self, keyword: str, limit: int) -> list[User]:
        stmt = (
            select(User)
            .where(
                User.isvalid == 1,
                User.is_active,
                User.is_approved,
                User.username.ilike(f"%{keyword}%"),
            )
            .order_by(User.create_time.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def update_fields(
        self,
        user: User,
        role: str | None = None,
        is_approved: bool | None = None,
        is_active: bool | None = None,
        updater_id: int | None = None,
    ) -> None:
        if role is not None:
            user.role = role
        if is_approved is not None:
            user.is_approved = is_approved
        if is_active is not None:
            user.is_active = is_active
        if updater_id is not None:
            user.updater_id = updater_id
        await self.session.flush()

    async def soft_delete(self, user: User, updater_id: int | None = None) -> None:
        user.isvalid = 0
        if updater_id is not None:
            user.updater_id = updater_id
        await self.session.flush()
