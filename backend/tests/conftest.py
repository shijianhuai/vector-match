import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
requires_db = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL 未设置,跳过集成测试")


@pytest.fixture(scope="session", autouse=True)
def _migrate_test_db():
    if not TEST_DATABASE_URL:
        return
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config("alembic.ini"), "head")


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()
    await engine.dispose()
