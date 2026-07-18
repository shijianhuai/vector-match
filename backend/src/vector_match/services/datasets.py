import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.core.exceptions import NotFoundError
from vector_match.db.models import Dataset
from vector_match.repositories.collections import CollectionRepository
from vector_match.repositories.data import DataRepository
from vector_match.repositories.datasets import DatasetRepository
from vector_match.repositories.tasks import TaskRepository


class DatasetService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.datasets = DatasetRepository(session)
        self.collections = CollectionRepository(session)
        self.data = DataRepository(session)
        self.tasks = TaskRepository(session)

    async def create(self, name: str, description: str = "", vector_model: str = "") -> Dataset:
        ds = await self.datasets.create(name=name, description=description, vector_model=vector_model)
        await self.session.commit()
        return ds

    async def list(self) -> list[Dataset]:
        return await self.datasets.list()

    async def detail(self, dataset_id: uuid.UUID) -> Dataset:
        ds = await self.datasets.get(dataset_id)
        if ds is None:
            raise NotFoundError("dataset not found")
        return ds

    async def update(self, dataset_id: uuid.UUID, name: str | None = None, description: str | None = None) -> Dataset:
        ds = await self.datasets.update(dataset_id, name=name, description=description)
        if ds is None:
            raise NotFoundError("dataset not found")
        await self.session.commit()
        return ds

    async def delete(self, dataset_id: uuid.UUID) -> None:
        ds = await self.datasets.get(dataset_id)
        if ds is None:
            raise NotFoundError("dataset not found")
        cols = await self.collections.list_by_dataset(dataset_id)
        col_ids = [c.id for c in cols]
        rows = await self.data.list_by_collections(col_ids)
        data_ids = [r.id for r in rows]
        await self.data.invalidate_indexes_for_data(data_ids)
        await self.data.soft_delete_many(data_ids)
        await self.tasks.fail_pending_for_data(data_ids)
        await self.collections.soft_delete_many(col_ids)
        await self.datasets.soft_delete(dataset_id)
        await self.session.commit()
