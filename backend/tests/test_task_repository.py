import uuid
from datetime import timedelta

from tests.conftest import requires_db
from vector_match.db.base import utcnow
from vector_match.repositories.tasks import TaskRepository

pytestmark = requires_db


async def test_enqueue_and_claim(db_session):
    repo = TaskRepository(db_session)
    data_ids = [uuid.uuid4(), uuid.uuid4()]
    await repo.enqueue_many(data_ids)
    tasks = await repo.claim(10)
    assert len(tasks) == 2
    assert all(t.status == "processing" for t in tasks)
    assert await repo.claim(10) == []


async def test_mark_done_and_failed(db_session):
    repo = TaskRepository(db_session)
    await repo.enqueue_many([uuid.uuid4()])
    (task,) = await repo.claim(1)
    await repo.mark_done(task.id)
    assert (await repo.get(task.id)).status == "done"
    await repo.mark_failed(task.id, "data deleted")
    got = await repo.get(task.id)
    assert got.status == "error" and got.last_error == "data deleted"


async def test_schedule_retry_backoff_then_error(db_session):
    repo = TaskRepository(db_session)
    await repo.enqueue_many([uuid.uuid4()])
    (task,) = await repo.claim(1)
    await repo.schedule_retry(task.id, "boom", max_attempts=3)
    got = await repo.get(task.id)
    assert got.status == "pending" and got.attempts == 1 and got.next_retry_at > utcnow()

    await repo.schedule_retry(task.id, "boom", max_attempts=1)
    got = await repo.get(task.id)
    assert got.status == "error" and got.attempts == 2


async def test_fail_pending_for_data(db_session):
    repo = TaskRepository(db_session)
    data_id = uuid.uuid4()
    await repo.enqueue_many([data_id, uuid.uuid4()])
    await repo.fail_pending_for_data([data_id])
    pending = await repo.claim(10)
    assert len(pending) == 1 and pending[0].data_id != data_id


async def test_reset_stale_processing(db_session):
    repo = TaskRepository(db_session)
    await repo.enqueue_many([uuid.uuid4()])
    (task,) = await repo.claim(1)
    task.update_time = utcnow() - timedelta(minutes=30)
    await db_session.flush()
    n = await repo.reset_stale_processing(stale_minutes=10)
    assert n == 1
    assert (await repo.get(task.id)).status == "pending"


async def test_reset_stale_processing_error_at_max_attempts(db_session):
    repo = TaskRepository(db_session)
    await repo.enqueue_many([uuid.uuid4()])
    (task,) = await repo.claim(1)
    task.attempts = 2
    task.update_time = utcnow() - timedelta(minutes=30)
    await db_session.flush()
    n = await repo.reset_stale_processing(stale_minutes=10, max_attempts=3)
    assert n == 1
    assert (await repo.get(task.id)).status == "error"
