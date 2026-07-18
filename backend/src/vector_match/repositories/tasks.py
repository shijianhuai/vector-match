import uuid
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.db.base import utcnow
from vector_match.db.models import TrainingTask


class TaskRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def enqueue_many(self, data_ids: list[uuid.UUID]) -> None:
        self.session.add_all([TrainingTask(data_id=d) for d in data_ids])
        await self.session.flush()

    async def claim(self, limit: int) -> list[TrainingTask]:
        stmt = (
            select(TrainingTask)
            .where(TrainingTask.status == "pending", TrainingTask.next_retry_at <= utcnow())
            .order_by(TrainingTask.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        tasks = list((await self.session.execute(stmt)).scalars().all())
        for t in tasks:
            t.status = "processing"
        await self.session.flush()
        return tasks

    async def get(self, task_id: uuid.UUID) -> TrainingTask | None:
        return await self.session.get(TrainingTask, task_id)

    async def mark_done(self, task_id: uuid.UUID) -> None:
        stmt = update(TrainingTask).where(TrainingTask.id == task_id).values(status="done")
        await self.session.execute(stmt)

    async def mark_failed(self, task_id: uuid.UUID, reason: str) -> None:
        stmt = update(TrainingTask).where(TrainingTask.id == task_id).values(status="error", last_error=reason[:500])
        await self.session.execute(stmt)

    async def schedule_retry(self, task_id: uuid.UUID, error: str, max_attempts: int) -> None:
        task = await self.get(task_id)
        if task is None:
            return
        task.attempts += 1
        task.last_error = error[:500]
        if task.attempts >= max_attempts:
            task.status = "error"
        else:
            task.status = "pending"
            task.next_retry_at = utcnow() + timedelta(minutes=min(2**task.attempts, 30))
        await self.session.flush()

    async def fail_pending_for_data(self, data_ids: list[uuid.UUID], reason: str = "data deleted") -> None:
        if not data_ids:
            return
        stmt = (
            update(TrainingTask)
            .where(TrainingTask.data_id.in_(data_ids), TrainingTask.status.in_(["pending", "processing"]))
            .values(status="error", last_error=reason)
        )
        await self.session.execute(stmt)

    async def reset_stale_processing(self, stale_minutes: int = 10) -> int:
        cutoff = utcnow() - timedelta(minutes=stale_minutes)
        stmt = (
            update(TrainingTask)
            .where(TrainingTask.status == "processing", TrainingTask.update_time < cutoff)
            .values(status="pending", next_retry_at=utcnow())
        )
        result = await self.session.execute(stmt)
        return result.rowcount
