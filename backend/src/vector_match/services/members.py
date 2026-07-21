import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.db.models import Dataset, DatasetMember, User
from vector_match.repositories.members import DatasetMemberRepository
from vector_match.repositories.users import UserRepository

ROLE_LEVEL = {"owner": 3, "editor": 2, "viewer": 1}
VALID_ROLES = ("owner", "editor", "viewer")


def _has_enough_role(member: DatasetMember | None, min_role: str) -> bool:
    if member is None:
        return False
    return ROLE_LEVEL[member.role] >= ROLE_LEVEL[min_role]


class MemberService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.members = DatasetMemberRepository(session)
        self.users = UserRepository(session)

    async def list_members(self, dataset_id: uuid.UUID) -> list[tuple[DatasetMember, User]]:
        rows = await self.members.list_by_dataset(dataset_id)
        user_ids = [r.user_id for r in rows]
        stmt = select(User).where(User.id.in_(user_ids), User.isvalid == 1)
        user_map = {u.id: u for u in (await self.session.execute(stmt)).scalars().all()}
        return [(r, user_map[r.user_id]) for r in rows if r.user_id in user_map]

    async def add_member(self, dataset_id: uuid.UUID, username: str, role: str) -> DatasetMember:
        if role not in VALID_ROLES:
            raise HTTPException(status_code=422, detail=f"role must be one of {VALID_ROLES}")
        username = username.lower().strip()
        user = await self.users.get_by_username(username)
        if user is None:
            raise HTTPException(status_code=404, detail="user not found")
        existing = await self.members.get_valid(dataset_id, user.id)
        if existing is not None:
            raise HTTPException(status_code=409, detail="member already exists")
        return await self.members.create(dataset_id, user.id, role)

    async def update_role(self, dataset_id: uuid.UUID, user_id: uuid.UUID, role: str) -> DatasetMember:
        if role not in VALID_ROLES:
            raise HTTPException(status_code=422, detail=f"role must be one of {VALID_ROLES}")
        member = await self.members.get_valid(dataset_id, user_id)
        if member is None:
            raise HTTPException(status_code=404, detail="member not found")
        if role == member.role:
            return member
        if member.role == "owner" and role != "owner":
            await self._ensure_not_last_owner(dataset_id)
        await self.members.update_role(member, role)
        await self.session.commit()
        return member

    async def remove_member(self, dataset_id: uuid.UUID, user_id: uuid.UUID) -> None:
        member = await self.members.get_valid(dataset_id, user_id)
        if member is None:
            raise HTTPException(status_code=404, detail="member not found")
        if member.role == "owner":
            await self._ensure_not_last_owner(dataset_id)
        await self.members.soft_delete(member)
        await self.session.commit()

    async def _ensure_not_last_owner(self, dataset_id: uuid.UUID) -> None:
        stmt = select(Dataset).where(Dataset.id == dataset_id, Dataset.isvalid == 1).with_for_update()
        await self.session.execute(stmt)
        owner_count = await self.members.count_valid_owners(dataset_id)
        if owner_count <= 1:
            raise HTTPException(status_code=422, detail="cannot remove or downgrade the last owner")

    async def get_member_role(self, dataset_id: uuid.UUID, user_id: uuid.UUID) -> str | None:
        member = await self.members.get_valid(dataset_id, user_id)
        return member.role if member else None
