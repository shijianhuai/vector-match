import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.db.models import Collection


class CollectionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, dataset_id: uuid.UUID, parent_id: uuid.UUID | None, name: str, type: str) -> Collection:
        col = Collection(dataset_id=dataset_id, parent_id=parent_id, name=name, type=type)
        self.session.add(col)
        await self.session.flush()
        return col

    async def get(self, collection_id: uuid.UUID) -> Collection | None:
        stmt = select(Collection).where(Collection.id == collection_id, Collection.isvalid == 1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_page(
        self,
        dataset_id: uuid.UUID,
        parent_id: uuid.UUID | None,
        offset: int,
        page_size: int,
        search_text: str | None,
    ) -> tuple[list[Collection], int]:
        conditions = [Collection.dataset_id == dataset_id, Collection.isvalid == 1]
        if parent_id is None:
            conditions.append(Collection.parent_id.is_(None))
        else:
            conditions.append(Collection.parent_id == parent_id)
        if search_text:
            conditions.append(Collection.name.ilike(f"%{search_text}%"))
        total = await self.session.scalar(select(func.count()).select_from(Collection).where(*conditions))
        stmt = (
            select(Collection)
            .where(*conditions)
            .order_by(Collection.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list((await self.session.execute(stmt)).scalars().all()), int(total or 0)

    async def update(self, collection_id: uuid.UUID, name: str | None = None) -> Collection | None:
        col = await self.get(collection_id)
        if col is None:
            return None
        if name is not None:
            col.name = name
        await self.session.flush()
        return col

    async def list_by_dataset(self, dataset_id: uuid.UUID) -> list[Collection]:
        stmt = select(Collection).where(Collection.dataset_id == dataset_id, Collection.isvalid == 1)
        return list((await self.session.execute(stmt)).scalars().all())

    async def soft_delete_many(self, collection_ids: list[uuid.UUID]) -> None:
        if not collection_ids:
            return
        stmt = update(Collection).where(Collection.id.in_(collection_ids)).values(isvalid=0)
        await self.session.execute(stmt)
