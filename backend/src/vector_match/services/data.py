import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.core.config import get_settings
from vector_match.core.exceptions import NotFoundError, ValidationError
from vector_match.db.models import DataIndex, DatasetData
from vector_match.repositories.collections import CollectionRepository
from vector_match.repositories.data import DataRepository
from vector_match.repositories.tasks import TaskRepository

MAX_BATCH = 200


@dataclass
class PushItem:
    q: str
    a: str | None = None
    key_id: str | None = None
    updatetime: datetime | None = None
    indexes: list[str] = field(default_factory=list)


class DataService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.collections = CollectionRepository(session)
        self.data = DataRepository(session)
        self.tasks = TaskRepository(session)

    async def push(
        self, collection_id: uuid.UUID, items: list[PushItem], operator_id: int | None = None
    ) -> tuple[int, int, int]:
        col = await self.collections.get(collection_id)
        if col is None:
            raise NotFoundError("collection not found")
        if col.type != "virtual":
            raise ValidationError("只能向 virtual 类型集合推送数据")
        if not 1 <= len(items) <= MAX_BATCH:
            raise ValidationError(f"每批数据量须在 1~{MAX_BATCH} 之间")
        max_custom = get_settings().max_custom_indexes
        for item in items:
            if len(item.indexes) > max_custom:
                raise ValidationError(f"自定义索引最多 {max_custom} 个")

        key_ids = [k for k in (item.key_id for item in items) if k is not None]
        dup_keys = {k for k in key_ids if key_ids.count(k) > 1}
        if dup_keys:
            raise ValidationError(f"批内 keyId 重复: {sorted(dup_keys)}")

        no_key_items = [item for item in items if item.key_id is None]
        key_items = [item for item in items if item.key_id is not None]

        existing_by_key: dict[str, DatasetData] = {}
        if key_items:
            rows = await self.data.list_valid_by_keys(
                col.dataset_id, [item.key_id for item in key_items if item.key_id]
            )
            existing_by_key = {row.key_id: row for row in rows if row.key_id}

        insert_len = update_len = skip_len = 0

        if no_key_items:
            rows = await self.data.create_many(
                [
                    {"dataset_id": col.dataset_id, "collection_id": col.id, "q": item.q, "a": item.a}
                    for item in no_key_items
                ],
                creator_id=operator_id,
            )
            for row, item in zip(rows, no_key_items, strict=True):
                await self.data.add_index(row.id, item.q, type="default", creator_id=operator_id)
                for text in item.indexes:
                    await self.data.add_index(row.id, text, type="custom", creator_id=operator_id)
            await self.tasks.enqueue_many([r.id for r in rows], creator_id=operator_id)
            insert_len += len(rows)

        custom_texts_cache: dict[uuid.UUID, set[str]] = {}

        for item in key_items:
            key_id = item.key_id
            assert key_id is not None
            existing = existing_by_key.get(key_id)
            if existing is None:
                try:
                    async with self.session.begin_nested():
                        row = await self._insert_one(col, item, operator_id)
                    insert_len += 1
                    existing_by_key[key_id] = row
                    continue
                except IntegrityError:
                    await self.session.rollback()
                    rows = await self.data.list_valid_by_keys(col.dataset_id, [key_id])
                    if not rows:
                        raise
                    existing = rows[0]
                    existing_by_key[key_id] = existing

            changed = await self._content_changed(existing, item, custom_texts_cache)
            if not changed:
                if item.updatetime is not None and item.updatetime != existing.source_updatetime:
                    await self.data.update_source_updatetime(existing.id, item.updatetime, updater_id=operator_id)
                skip_len += 1
            else:
                existing.q = item.q
                existing.a = item.a
                if item.updatetime is not None:
                    existing.source_updatetime = item.updatetime
                if operator_id is not None:
                    existing.updater_id = operator_id
                await self.session.flush()
                await self._rebuild_indexes(existing.id, item, operator_id)
                await self.tasks.enqueue_many([existing.id], creator_id=operator_id)
                update_len += 1

        await self.session.commit()
        return insert_len, update_len, skip_len

    async def _insert_one(self, col, item: PushItem, operator_id: int | None) -> DatasetData:
        rows = await self.data.create_many(
            [
                {
                    "dataset_id": col.dataset_id,
                    "collection_id": col.id,
                    "q": item.q,
                    "a": item.a,
                    "key_id": item.key_id,
                    "source_updatetime": item.updatetime,
                }
            ],
            creator_id=operator_id,
        )
        row = rows[0]
        await self.data.add_index(row.id, item.q, type="default", creator_id=operator_id)
        for text in item.indexes:
            await self.data.add_index(row.id, text, type="custom", creator_id=operator_id)
        await self.tasks.enqueue_many([row.id], creator_id=operator_id)
        return row

    async def _rebuild_indexes(self, data_id: uuid.UUID, item: PushItem, operator_id: int | None) -> None:
        await self.data.invalidate_indexes(data_id)
        await self.data.add_index(data_id, item.q, type="default", creator_id=operator_id)
        for text in item.indexes:
            await self.data.add_index(data_id, text, type="custom", creator_id=operator_id)

    async def _content_changed(self, existing: DatasetData, item: PushItem, cache: dict[uuid.UUID, set[str]]) -> bool:
        if existing.q != item.q:
            return True
        if existing.a != item.a:
            return True
        if existing.id not in cache:
            cache.update(await self.data.list_custom_index_texts([existing.id]))
        existing_custom = cache.get(existing.id, set())
        new_custom = set(item.indexes)
        return existing_custom != new_custom

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
        max_custom = get_settings().max_custom_indexes
        if indexes is not None and len(indexes) > max_custom:
            raise ValidationError(f"自定义索引最多 {max_custom} 个")
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
        await self._delete_many([data_id], operator_id)
        await self.session.commit()

    async def delete_by_keys(self, collection_id: uuid.UUID, key_ids: list[str], operator_id: int | None = None) -> int:
        col = await self.collections.get(collection_id)
        if col is None:
            raise NotFoundError("collection not found")
        if not 1 <= len(key_ids) <= MAX_BATCH:
            raise ValidationError(f"每批 keyId 数量须在 1~{MAX_BATCH} 之间")
        rows = await self.data.list_valid_by_keys(col.dataset_id, key_ids)
        if rows:
            await self._delete_many([r.id for r in rows], operator_id)
            await self.session.commit()
        return len(rows)

    async def _delete_many(self, data_ids: list[uuid.UUID], operator_id: int | None) -> None:
        await self.data.invalidate_indexes_for_data(data_ids)
        await self.data.soft_delete_many(data_ids, updater_id=operator_id)
        await self.tasks.fail_pending_for_data(data_ids)

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
