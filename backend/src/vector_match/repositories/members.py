import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.db.models import DatasetMember


class DatasetMemberRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        dataset_id: uuid.UUID,
        user_id: int,
        role: str,
        creator_id: int | None = None,
    ) -> DatasetMember:
        member = DatasetMember(
            dataset_id=dataset_id,
            user_id=user_id,
            role=role,
            creator_id=creator_id,
            updater_id=creator_id,
        )
        self.session.add(member)
        await self.session.flush()
        return member

    async def get_by_id(self, member_id: uuid.UUID) -> DatasetMember | None:
        stmt = select(DatasetMember).where(DatasetMember.id == member_id, DatasetMember.isvalid == 1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_valid(self, dataset_id: uuid.UUID, user_id: int) -> DatasetMember | None:
        stmt = select(DatasetMember).where(
            DatasetMember.dataset_id == dataset_id,
            DatasetMember.user_id == user_id,
            DatasetMember.isvalid == 1,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_by_dataset(self, dataset_id: uuid.UUID) -> list[DatasetMember]:
        stmt = (
            select(DatasetMember)
            .where(DatasetMember.dataset_id == dataset_id, DatasetMember.isvalid == 1)
            .order_by(DatasetMember.create_time.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_dataset_ids_by_user(self, user_id: int) -> list[uuid.UUID]:
        stmt = (
            select(DatasetMember.dataset_id)
            .where(DatasetMember.user_id == user_id, DatasetMember.isvalid == 1)
            .distinct()
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def update_role(
        self, member: DatasetMember, role: str, updater_id: int | None = None
    ) -> None:
        member.role = role
        if updater_id is not None:
            member.updater_id = updater_id
        await self.session.flush()

    async def soft_delete(
        self, member: DatasetMember, updater_id: int | None = None
    ) -> None:
        member.isvalid = 0
        if updater_id is not None:
            member.updater_id = updater_id
        await self.session.flush()

    async def count_valid_owners(self, dataset_id: uuid.UUID) -> int:
        stmt = select(DatasetMember).where(
            DatasetMember.dataset_id == dataset_id,
            DatasetMember.role == "owner",
            DatasetMember.isvalid == 1,
        )
        return len((await self.session.execute(stmt)).scalars().all())

    async def has_any_valid_member(self, dataset_id: uuid.UUID) -> bool:
        stmt = select(DatasetMember).where(
            DatasetMember.dataset_id == dataset_id, DatasetMember.isvalid == 1
        ).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    async def list_dataset_ids_without_owner(self) -> list[uuid.UUID]:
        from vector_match.db.models import Dataset

        stmt = (
            select(Dataset.id)
            .where(Dataset.isvalid == 1)
            .where(
                ~select(1)
                .where(
                    DatasetMember.dataset_id == Dataset.id,
                    DatasetMember.role == "owner",
                    DatasetMember.isvalid == 1,
                )
                .exists()
            )
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_or_create(
        self,
        dataset_id: uuid.UUID,
        user_id: int,
        role: str,
        creator_id: int | None = None,
    ) -> DatasetMember:
        existing = await self.get_valid(dataset_id, user_id)
        if existing is not None:
            return existing
        return await self.create(dataset_id, user_id, role, creator_id=creator_id)
