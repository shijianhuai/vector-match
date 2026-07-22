import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.core.exceptions import NotFoundError, ValidationError
from vector_match.db.models import Collection
from vector_match.repositories.collections import CollectionRepository
from vector_match.repositories.data import DataRepository
from vector_match.repositories.datasets import DatasetRepository
from vector_match.repositories.tasks import TaskRepository

VALID_TYPES = ("folder", "virtual")


class CollectionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.collections = CollectionRepository(session)
        self.datasets = DatasetRepository(session)
        self.data = DataRepository(session)
        self.tasks = TaskRepository(session)

    async def create(
        self, dataset_id: uuid.UUID, parent_id: uuid.UUID | None, name: str, type: str, operator_id: int | None = None
    ) -> Collection:
        if type not in VALID_TYPES:
            raise ValidationError(f"type 必须是 {VALID_TYPES} 之一")
        if await self.datasets.get(dataset_id) is None:
            raise NotFoundError("dataset not found")
        if parent_id is not None and await self.collections.get(parent_id) is None:
            raise NotFoundError("parent collection not found")
        col = await self.collections.create(
            dataset_id=dataset_id, parent_id=parent_id, name=name, type=type, creator_id=operator_id
        )
        await self.session.commit()
        return col

    async def list_page(self, dataset_id, parent_id, offset, page_size, search_text):
        return await self.collections.list_page(dataset_id, parent_id, offset, page_size, search_text)

    async def detail(self, collection_id: uuid.UUID) -> Collection:
        col = await self.collections.get(collection_id)
        if col is None:
            raise NotFoundError("collection not found")
        return col

    async def update(self, collection_id: uuid.UUID, name: str | None = None, operator_id: int | None = None) -> Collection:
        col = await self.collections.update(collection_id, name=name, updater_id=operator_id)
        if col is None:
            raise NotFoundError("collection not found")
        await self.session.commit()
        return col

    async def delete(self, collection_ids: list[uuid.UUID], operator_id: int | None = None) -> None:
        all_ids = await self._collect_with_children(collection_ids)
        rows = await self.data.list_by_collections(all_ids)
        data_ids = [r.id for r in rows]
        await self.data.invalidate_indexes_for_data(data_ids)
        await self.data.soft_delete_many(data_ids, updater_id=operator_id)
        await self.tasks.fail_pending_for_data(data_ids)
        await self.collections.soft_delete_many(all_ids, updater_id=operator_id)
        await self.session.commit()

    async def _collect_with_children(self, collection_ids: list[uuid.UUID]) -> list[uuid.UUID]:
        seen = set(collection_ids)
        frontier = list(collection_ids)
        while frontier:
            children = await self.collections.list_by_parents(frontier)
            frontier = [c.id for c in children if c.id not in seen]
            seen.update(frontier)
        return list(seen)
