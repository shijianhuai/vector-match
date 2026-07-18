import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.db.models import Dataset


class DatasetRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, name: str, description: str, vector_model: str) -> Dataset:
        ds = Dataset(name=name, description=description, vector_model=vector_model)
        self.session.add(ds)
        await self.session.flush()
        return ds

    async def get(self, dataset_id: uuid.UUID) -> Dataset | None:
        stmt = select(Dataset).where(Dataset.id == dataset_id, Dataset.isvalid == 1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list(self) -> list[Dataset]:
        stmt = select(Dataset).where(Dataset.isvalid == 1).order_by(Dataset.create_time.desc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def update(
        self, dataset_id: uuid.UUID, name: str | None = None, description: str | None = None
    ) -> Dataset | None:
        ds = await self.get(dataset_id)
        if ds is None:
            return None
        if name is not None:
            ds.name = name
        if description is not None:
            ds.description = description
        await self.session.flush()
        return ds

    async def soft_delete(self, dataset_id: uuid.UUID) -> None:
        stmt = update(Dataset).where(Dataset.id == dataset_id).values(isvalid=0)
        await self.session.execute(stmt)
