import os

import httpx
import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
requires_db = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL 未设置,跳过集成测试")


@pytest.fixture(scope="session", autouse=True)
def _set_test_env():
    if TEST_DATABASE_URL:
        os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    os.environ.setdefault("JWT_SECRET", "test-jwt-secret-key-with-at-least-32-bytes")
    os.environ.setdefault("ADMIN_USERNAME", "test-admin")
    os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
    # 确保每个测试会话都使用最新环境变量实例化 Settings
    from vector_match.core.config import get_settings

    get_settings.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def _migrate_test_db(_set_test_env):
    if not TEST_DATABASE_URL:
        return
    db_name = TEST_DATABASE_URL.rsplit("/", 1)[-1].split("?")[0]
    if "test" not in db_name:
        pytest.exit(
            f"TEST_DATABASE_URL 指向的库 {db_name!r} 不是测试库(库名需含 'test'), "
            "部分测试会物理清表, 为防止误删开发数据已中止。请使用独立测试库, 如 vector_match_test"
        )
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


@pytest_asyncio.fixture
async def api_app(db_session):
    from vector_match.api.deps import get_db
    from vector_match.main import create_app

    app = create_app()

    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    async with LifespanManager(app):
        yield app


@pytest.fixture
def make_user(db_session):
    from vector_match.services.users import UserService

    async def _make(
        username: str,
        password: str = "password",
        is_superuser: bool = False,
        allow_api_key: bool = False,
    ):
        svc = UserService(db_session)
        user = await svc.create_user(
            username=username, password=password, is_superuser=is_superuser
        )
        if allow_api_key and not is_superuser:
            user.allow_api_key = True
            await db_session.commit()
        return user

    return _make


@pytest.fixture
async def superuser(make_user):
    import uuid

    return await make_user(f"superuser-{uuid.uuid4().hex[:8]}", "superpass", is_superuser=True)


@pytest.fixture
async def auth_headers(superuser):
    from vector_match.core.config import get_settings
    from vector_match.core.security import create_access_token

    settings = get_settings()
    token = create_access_token(str(superuser.id), settings)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def client(api_app, auth_headers):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api_app),
        base_url="http://test",
        headers=auth_headers,
    ) as c:
        yield c
