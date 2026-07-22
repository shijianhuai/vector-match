import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.core.exceptions import NotFoundError, ValidationError
from vector_match.db.models import DataIndex, DatasetData
from vector_match.repositories.collections import CollectionRepository
from vector_match.repositories.data import DataRepository
from vector_match.repositories.tasks import TaskRepository

MAX_BATCH = 200
MAX_CUSTOM_INDEXES = 5


@dataclass
class PushItem:
    q: str
    a: str | None = None
    indexes: list[str] = field(default_factory=list)


class DataService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.collections = CollectionRepository(session)
        self.data = DataRepository(session)
        self.tasks = TaskRepository(session)

    async def push(self, collection_id: uuid.UUID, items: list[PushItem], operator_id: int | None = None) -> int:
        col = await self.collections.get(collection_id)
        if col is None:
            raise NotFoundError("collection not found")
        if col.type != "virtual":
            raise ValidationError("只能向 virtual 类型集合推送数据")
        if not 1 <= len(items) <= MAX_BATCH:
            raise ValidationError(f"每批数据量须在 1~{MAX_BATCH} 之间")
        for item in items:
            if len(item.indexes) > MAX_CUSTOM_INDEXES:
                raise ValidationError(f"自定义索引最多 {MAX_CUSTOM_INDEXES} 个")

        rows = await self.data.create_many(
            [{"dataset_id": col.dataset_id, "collection_id": col.id, "q": item.q, "a": item.a} for item in items],
            creator_id=operator_id,
        )
        for row, item in zip(rows, items, strict=True):
            await self.data.add_index(row.id, item.q, type="default", creator_id=operator_id)
            for text in item.indexes:
                await self.data.add_index(row.id, text, type="custom", creator_id=operator_id)
        await self.tasks.enqueue_many([r.id for r in rows], creator_id=operator_id)
        await self.session.commit()
        return len(rows)

    async def update(
        self,
        data_id: uuid.UUID,
        q: str | None = None,
        a: str | None = None,
        indexes: list[str] | None = None,
        operator_id: int | None = None,
    ) -> None:
        obj = await self.data.get(data_id)
        if obj is None:
            raise NotFoundError("data not found")
        if indexes is not None and len(indexes) > MAX_CUSTOM_INDEXES:
            raise ValidationError(f"自定义索引最多 {MAX_CUSTOM_INDEXES} 个")
        new_q = q if q is not None else obj.q
        await self.data.update_fields(data_id, q=q, a=a, updater_id=operator_id)
        await self.data.invalidate_indexes(data_id)
        await self.data.add_index(data_id, new_q, type="default", creator_id=operator_id)
        for text in indexes or []:
            await self.data.add_index(data_id, text, type="custom", creator_id=operator_id)
        await self.tasks.enqueue_many([data_id], creator_id=operator_id)
        await self.session.commit()

    async def delete(self, data_id: uuid.UUID, operator_id: int | None = None) -> None:
        obj = await self.data.get(data_id)
        if obj is None:
            raise NotFoundError("data not found")
        await self.data.invalidate_indexes(data_id)
        await self.data.soft_delete_many([data_id], updater_id=operator_id)
        await self.tasks.fail_pending_for_data([data_id])
        await self.session.commit()

    async def list_page(
        self, collection_id: uuid.UUID, offset: int, page_size: int, search_text: str | None
    ) -> tuple[list[DatasetData], int, set[uuid.UUID]]:
        items, total = await self.data.list_page(collection_id, offset, page_size, search_text)
        trained = await self.data.list_trained_data_ids([i.id for i in items])
        return items, total, trained

    async def detail(self, data_id: uuid.UUID) -> tuple[DatasetData, list[DataIndex], bool]:
        obj = await self.data.get(data_id)
        if obj is None:
            raise NotFoundError("data not found")
        indexes = await self.data.list_valid_indexes(data_id)
        trained = data_id in await self.data.list_trained_data_ids([data_id])
        return obj, indexes, trained
