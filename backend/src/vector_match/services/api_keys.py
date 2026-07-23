import secrets

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.db.models import ApiKey, User
from vector_match.repositories.api_keys import ApiKeyRepository


class ApiKeyService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.keys = ApiKeyRepository(session)

    def _generate_key(self) -> str:
        return f"sk-{secrets.token_hex(16)}"

    async def create_key(self, user: User, name: str) -> ApiKey:
        name = name.strip()
        if len(name) < 1 or len(name) > 128:
            raise HTTPException(status_code=422, detail="name must be 1-128 characters")
        key_value = self._generate_key()
        key = await self.keys.create(
            user_id=user.id, name=name, key=key_value, creator_id=user.id
        )
        await self.session.commit()
        return key

    async def list_keys(
        self, user: User, offset: int, page_size: int
    ) -> tuple[list[ApiKey], int]:
        return await self.keys.list_by_user(user.id, offset, page_size)

    async def update_key(self, user: User, key_id: int, name: str) -> ApiKey:
        name = name.strip()
        if len(name) < 1 or len(name) > 128:
            raise HTTPException(status_code=422, detail="name must be 1-128 characters")
        key = await self.keys.get_by_id(key_id)
        if key is None or key.user_id != user.id:
            raise HTTPException(status_code=404, detail="api key not found")
        await self.keys.update_name(key, name, updater_id=user.id)
        await self.session.commit()
        return key

    async def delete_key(self, user: User, key_id: int) -> None:
        key = await self.keys.get_by_id(key_id)
        if key is None or key.user_id != user.id:
            raise HTTPException(status_code=404, detail="api key not found")
        await self.keys.soft_delete(key, updater_id=user.id)
        await self.session.commit()
