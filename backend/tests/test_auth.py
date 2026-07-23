from datetime import UTC, datetime, timedelta

import jwt
import pytest_asyncio

from tests.conftest import requires_db

pytestmark = requires_db


@pytest_asyncio.fixture
async def client_no_auth(api_app):
    import httpx

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api_app), base_url="http://test") as c:
        yield c


async def test_register_success(client_no_auth):
    resp = await client_no_auth.post(
        "/api/auth/register", json={"username": "alice", "password": "secret123", "email": "a@example.com"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "id" in body


async def test_register_duplicate_username(client_no_auth):
    await client_no_auth.post("/api/auth/register", json={"username": "bob", "password": "secret123"})
    resp = await client_no_auth.post("/api/auth/register", json={"username": "Bob", "password": "secret123"})
    assert resp.status_code == 409
    assert "detail" in resp.json()


async def test_login_success(client_no_auth, make_user):
    await make_user("charlie", "secret123")
    resp = await client_no_auth.post(
        "/api/auth/login", json={"username": "Charlie", "password": "secret123"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body and "user" in body
    assert body["user"]["username"] == "charlie"
    assert body["user"]["role"] == "user"


async def test_login_wrong_password(client_no_auth, make_user):
    await make_user("dave", "secret123")
    resp = await client_no_auth.post(
        "/api/auth/login", json={"username": "dave", "password": "wrong"}
    )
    assert resp.status_code == 401
    assert "detail" in resp.json()


async def test_login_disabled_user(client_no_auth, db_session):
    from vector_match.services.users import UserService

    svc = UserService(db_session)
    user = await svc.create_user(username="eve", password="secret123", is_approved=True)
    user.is_active = False
    await db_session.commit()

    resp = await client_no_auth.post(
        "/api/auth/login", json={"username": "eve", "password": "secret123"}
    )
    assert resp.status_code == 401


async def test_login_unapproved_user(client_no_auth):
    await client_no_auth.post("/api/auth/register", json={"username": "pending", "password": "secret123"})
    resp = await client_no_auth.post(
        "/api/auth/login", json={"username": "pending", "password": "secret123"}
    )
    assert resp.status_code == 401
    assert "审核" in resp.json()["detail"]


async def test_me_normal(client_no_auth, make_user):
    from vector_match.core.config import get_settings
    from vector_match.core.security import create_access_token

    user = await make_user("frank", "secret123", role="superadmin")
    settings = get_settings()
    token = create_access_token(str(user.id), settings)
    resp = await client_no_auth.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "frank"
    assert body["role"] == "superadmin"


async def test_me_no_token(client_no_auth):
    resp = await client_no_auth.get("/api/auth/me")
    assert resp.status_code == 401


async def test_me_fake_token(client_no_auth):
    resp = await client_no_auth.get("/api/auth/me", headers={"Authorization": "Bearer fake-token"})
    assert resp.status_code == 401


async def test_me_expired_token(client_no_auth, make_user):
    from vector_match.core.config import get_settings

    user = await make_user("grace", "secret123")
    settings = get_settings()
    exp = datetime.now(UTC) - timedelta(minutes=1)
    token = jwt.encode({"sub": str(user.id), "exp": exp}, settings.jwt_secret, algorithm="HS256")
    resp = await client_no_auth.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


async def test_me_disabled_user_token(client_no_auth, db_session, make_user):
    from vector_match.core.config import get_settings
    from vector_match.core.security import create_access_token

    user = await make_user("heidi", "secret123")
    settings = get_settings()
    token = create_access_token(str(user.id), settings)
    user.is_active = False
    await db_session.commit()
    resp = await client_no_auth.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


async def test_register_duplicate_email(client_no_auth):
    await client_no_auth.post(
        "/api/auth/register",
        json={"username": "alice1", "password": "secret123", "email": "dup@example.com"},
    )
    resp = await client_no_auth.post(
        "/api/auth/register",
        json={"username": "alice2", "password": "secret123", "email": "Dup@example.com"},
    )
    assert resp.status_code == 409
    assert "detail" in resp.json()


async def test_me_invalid_sub_token(client_no_auth):
    from vector_match.core.config import get_settings

    settings = get_settings()
    token = jwt.encode({"sub": "not-an-int"}, settings.jwt_secret, algorithm="HS256")
    resp = await client_no_auth.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert "detail" in resp.json()


async def test_register_after_soft_delete(client_no_auth, db_session):
    import uuid

    from vector_match.services.users import UserService

    username = f"reuser-{uuid.uuid4().hex[:8]}"
    svc = UserService(db_session)
    user = await svc.create_user(username=username, password="secret123")
    await svc.users.soft_delete(user)
    # db_session 在 fixture 中统一回滚, client 复用同一 session 即可看到 isvalid=0

    resp = await client_no_auth.post(
        "/api/auth/register", json={"username": username, "password": "newsecret123"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "id" in body
