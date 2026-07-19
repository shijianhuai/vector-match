import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests.conftest import TEST_DATABASE_URL, requires_db
from vector_match.core.config import Settings
from vector_match.providers.embedding import EmbeddingError
from vector_match.repositories.collections import CollectionRepository
from vector_match.repositories.data import DataRepository
from vector_match.repositories.datasets import DatasetRepository
from vector_match.repositories.tasks import TaskRepository
from vector_match.services.data import DataService, PushItem
from vector_match.worker.trainer import process_batch

pytestmark = requires_db


class FakeEmbedding:
    def __init__(self, fail: bool = False):
        self._fail = fail

    async def embed(self, texts):
        if self._fail:
            raise EmbeddingError("boom")
        return [[0.1] * 1024 for _ in texts]


@pytest_asyncio.fixture
async def worker_env():
    """worker 自行开会话并 commit, 不能用回滚夹具; 测试后清表。"""
    engine = create_async_engine(TEST_DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    async with engine.begin() as conn:
        for table in ("training_tasks", "data_indexes", "dataset_data", "collections", "datasets"):
            await conn.execute(text(f"DELETE FROM {table}"))
    await engine.dispose()


async def _seed(worker_env) -> None:
    async with worker_env() as session:
        ds = await DatasetRepository(session).create(name="d", description="", vector_model="m")
        col = await CollectionRepository(session).create(dataset_id=ds.id, parent_id=None, name="c", type="virtual")
        await session.commit()
        await DataService(session).push(col.id, [PushItem(q="易方达蓝筹精选混合", a="005827", indexes=["易方达蓝筹"])])


async def _claim(worker_env):
    async with worker_env() as session:
        tasks = await TaskRepository(session).claim(10)
        await session.commit()
        return tasks


async def test_process_batch_trains(worker_env):
    await _seed(worker_env)
    tasks = await _claim(worker_env)
    assert len(tasks) == 1

    await process_batch(worker_env, FakeEmbedding(), Settings(worker_concurrency=2), tasks)

    async with worker_env() as session:
        assert (await TaskRepository(session).get(tasks[0].id)).status == "done"
        data_repo = DataRepository(session)
        data = await data_repo.get(tasks[0].data_id)
        assert data.full_text_tokens != ""
        indexes = await data_repo.list_valid_indexes(data.id)
        assert len(indexes) == 2
        assert all(i.vector is not None for i in indexes)
        assert data.id in await data_repo.list_trained_data_ids([data.id])


async def test_process_batch_retries_on_embedding_error(worker_env):
    await _seed(worker_env)
    tasks = await _claim(worker_env)

    await process_batch(worker_env, FakeEmbedding(fail=True), Settings(), tasks)

    async with worker_env() as session:
        task = await TaskRepository(session).get(tasks[0].id)
        assert task.status == "pending"
        assert task.attempts == 1
        assert "boom" in task.last_error


async def test_process_batch_marks_deleted_data(worker_env):
    await _seed(worker_env)
    tasks = await _claim(worker_env)
    async with worker_env() as session:
        await DataRepository(session).soft_delete_many([tasks[0].data_id])
        await session.commit()

    await process_batch(worker_env, FakeEmbedding(), Settings(), tasks)

    async with worker_env() as session:
        task = await TaskRepository(session).get(tasks[0].id)
        assert task.status == "error" and task.last_error == "data deleted"
