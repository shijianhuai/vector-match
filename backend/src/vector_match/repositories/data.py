import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.db.models import DataIndex, DatasetData


class DataRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_many(
        self, rows: list[dict], creator_id: int | None = None
    ) -> list[DatasetData]:
        if creator_id is not None:
            for row in rows:
                row.setdefault("creator_id", creator_id)
                row.setdefault("updater_id", creator_id)
        objs = [DatasetData(**row) for row in rows]
        self.session.add_all(objs)
        await self.session.flush()
        return objs

    async def get(self, data_id: uuid.UUID) -> DatasetData | None:
        stmt = select(DatasetData).where(DatasetData.id == data_id, DatasetData.isvalid == 1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_page(
        self, collection_id: uuid.UUID, offset: int, page_size: int, search_text: str | None
    ) -> tuple[list[DatasetData], int]:
        conditions = [DatasetData.collection_id == collection_id, DatasetData.isvalid == 1]
        if search_text:
            conditions.append(DatasetData.q.ilike(f"%{search_text}%"))
        total = await self.session.scalar(
            select(func.count()).select_from(DatasetData).where(*conditions)
        )
        stmt = (
            select(DatasetData)
            .where(*conditions)
            .order_by(DatasetData.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list((await self.session.execute(stmt)).scalars().all()), int(total or 0)

    async def list_by_ids(self, data_ids: list[uuid.UUID]) -> list[DatasetData]:
        if not data_ids:
            return []
        stmt = select(DatasetData).where(DatasetData.id.in_(data_ids), DatasetData.isvalid == 1)
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_by_collections(self, collection_ids: list[uuid.UUID]) -> list[DatasetData]:
        if not collection_ids:
            return []
        stmt = select(DatasetData).where(
            DatasetData.collection_id.in_(collection_ids), DatasetData.isvalid == 1
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def update_fields(
        self,
        data_id: uuid.UUID,
        q: str | None = None,
        a: str | None = None,
        updater_id: int | None = None,
    ) -> None:
        obj = await self.get(data_id)
        if obj is None:
            return
        if q is not None:
            obj.q = q
        if a is not None:
            obj.a = a
        if updater_id is not None:
            obj.updater_id = updater_id
        await self.session.flush()

    async def set_full_text_tokens(self, data_id: uuid.UUID, tokens: str) -> None:
        stmt = update(DatasetData).where(DatasetData.id == data_id).values(full_text_tokens=tokens)
        await self.session.execute(stmt)

    async def soft_delete_many(
        self, data_ids: list[uuid.UUID], updater_id: int | None = None
    ) -> None:
        if not data_ids:
            return
        stmt = update(DatasetData).where(DatasetData.id.in_(data_ids)).values(
            isvalid=0, updater_id=updater_id
        )
        await self.session.execute(stmt)

    async def add_index(
        self, data_id: uuid.UUID, text: str, type: str = "custom", creator_id: int | None = None
    ) -> DataIndex:
        idx = DataIndex(
            data_id=data_id, text=text, type=type, creator_id=creator_id, updater_id=creator_id
        )
        self.session.add(idx)
        await self.session.flush()
        return idx

    async def list_valid_indexes(self, data_id: uuid.UUID, only_untrained: bool = False) -> list[DataIndex]:
        conditions = [DataIndex.data_id == data_id, DataIndex.isvalid == 1]
        if only_untrained:
            conditions.append(DataIndex.vector.is_(None))
        stmt = select(DataIndex).where(*conditions).order_by(DataIndex.create_time)
        return list((await self.session.execute(stmt)).scalars().all())

    async def invalidate_indexes(self, data_id: uuid.UUID) -> None:
        await self.invalidate_indexes_for_data([data_id])

    async def invalidate_indexes_for_data(self, data_ids: list[uuid.UUID]) -> None:
        if not data_ids:
            return
        stmt = update(DataIndex).where(DataIndex.data_id.in_(data_ids)).values(isvalid=0)
        await self.session.execute(stmt)

    async def set_index_vector(self, index_id: uuid.UUID, vector: list[float]) -> None:
        stmt = update(DataIndex).where(DataIndex.id == index_id).values(vector=vector)
        await self.session.execute(stmt)

    async def list_trained_data_ids(self, data_ids: list[uuid.UUID]) -> set[uuid.UUID]:
        if not data_ids:
            return set()
        stmt = (
            select(DataIndex.data_id)
            .where(
                DataIndex.data_id.in_(data_ids),
                DataIndex.isvalid == 1,
                DataIndex.type == "default",
                DataIndex.vector.is_not(None),
            )
            .distinct()
        )
        return set((await self.session.execute(stmt)).scalars().all())
