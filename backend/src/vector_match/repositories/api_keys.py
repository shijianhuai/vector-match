from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.db.base import utcnow
from vector_match.db.models import ApiKey


class ApiKeyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self, user_id: int, name: str, key: str, creator_id: int | None = None
    ) -> ApiKey:
        api_key = ApiKey(
            user_id=user_id,
            name=name,
            key=key,
            creator_id=creator_id,
            updater_id=creator_id,
        )
        self.session.add(api_key)
        await self.session.flush()
        return api_key

    async def get_by_id(self, key_id: int) -> ApiKey | None:
        stmt = select(ApiKey).where(ApiKey.id == key_id, ApiKey.isvalid == 1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_key(self, key: str) -> ApiKey | None:
        stmt = select(ApiKey).where(ApiKey.key == key, ApiKey.isvalid == 1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_by_user(
        self, user_id: int, offset: int, page_size: int
    ) -> tuple[list[ApiKey], int]:
        stmt_total = (
            select(func.count())
            .select_from(ApiKey)
            .where(ApiKey.user_id == user_id, ApiKey.isvalid == 1)
        )
        total = await self.session.scalar(stmt_total)
        stmt = (
            select(ApiKey)
            .where(ApiKey.user_id == user_id, ApiKey.isvalid == 1)
            .order_by(ApiKey.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list((await self.session.execute(stmt)).scalars().all()), int(total or 0)

    async def update_name(
        self, api_key: ApiKey, name: str, updater_id: int | None = None
    ) -> None:
        api_key.name = name
        if updater_id is not None:
            api_key.updater_id = updater_id
        await self.session.flush()

    async def soft_delete(
        self, api_key: ApiKey, updater_id: int | None = None
    ) -> None:
        api_key.isvalid = 0
        if updater_id is not None:
            api_key.updater_id = updater_id
        await self.session.flush()

    async def touch_last_used(self, api_key: ApiKey) -> None:
        api_key.last_used_at = utcnow()
        await self.session.flush()
