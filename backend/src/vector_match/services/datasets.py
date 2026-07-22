import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.core.exceptions import NotFoundError
from vector_match.db.models import Dataset, User
from vector_match.repositories.collections import CollectionRepository
from vector_match.repositories.data import DataRepository
from vector_match.repositories.datasets import DatasetRepository
from vector_match.repositories.members import DatasetMemberRepository
from vector_match.repositories.tasks import TaskRepository


class DatasetService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.datasets = DatasetRepository(session)
        self.collections = CollectionRepository(session)
        self.data = DataRepository(session)
        self.tasks = TaskRepository(session)
        self.members = DatasetMemberRepository(session)

    async def create(self, user: User, name: str, description: str = "", vector_model: str = "") -> Dataset:
        ds = await self.datasets.create(
            name=name, description=description, vector_model=vector_model, creator_id=user.id
        )
        await self.members.create(ds.id, user.id, "owner", creator_id=user.id)
        await self.session.commit()
        return ds

    async def list(self, user: User | None = None) -> list[tuple[Dataset, str]]:
        if user is None or user.is_superuser:
            items = await self.datasets.list()
            return [(ds, "owner") for ds in items]
        dataset_ids = await self.members.list_dataset_ids_by_user(user.id)
        if not dataset_ids:
            return []
        items = await self.datasets.list_by_ids(dataset_ids)
        members = [await self.members.get_valid(ds.id, user.id) for ds in items]
        return [(ds, member.role if member else "viewer") for ds, member in zip(items, members, strict=True)]

    async def detail(self, dataset_id: uuid.UUID, user: User | None = None) -> tuple[Dataset, str]:
        ds = await self.datasets.get(dataset_id)
        if ds is None:
            raise NotFoundError("dataset not found")
        role = "owner"
        if user is not None and not user.is_superuser:
            member = await self.members.get_valid(dataset_id, user.id)
            if member is None:
                raise HTTPException(status_code=403, detail="permission denied")
            role = member.role
        return ds, role

    async def update(
        self, dataset_id: uuid.UUID, name: str | None = None, description: str | None = None, operator_id: int | None = None
    ) -> Dataset:
        ds = await self.datasets.update(dataset_id, name=name, description=description, updater_id=operator_id)
        if ds is None:
            raise NotFoundError("dataset not found")
        await self.session.commit()
        return ds

    async def delete(self, dataset_id: uuid.UUID, operator_id: int | None = None) -> None:
        ds = await self.datasets.get(dataset_id)
        if ds is None:
            raise NotFoundError("dataset not found")
        cols = await self.collections.list_by_dataset(dataset_id)
        col_ids = [c.id for c in cols]
        rows = await self.data.list_by_collections(col_ids)
        data_ids = [r.id for r in rows]
        await self.data.invalidate_indexes_for_data(data_ids)
        await self.data.soft_delete_many(data_ids, updater_id=operator_id)
        await self.tasks.fail_pending_for_data(data_ids)
        await self.collections.soft_delete_many(col_ids, updater_id=operator_id)
        await self.datasets.soft_delete(dataset_id, updater_id=operator_id)
        await self.session.commit()
