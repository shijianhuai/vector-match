import uuid

import httpx

from tests.conftest import requires_db
from vector_match.api.deps import get_embedding, get_rerank
from vector_match.core.config import get_settings
from vector_match.core.security import create_access_token
from vector_match.repositories.members import DatasetMemberRepository
from vector_match.services.collections import CollectionService
from vector_match.services.datasets import DatasetService

pytestmark = requires_db

DIM = 1024


class FakeEmbedding:
    async def embed(self, texts):
        return [[1.0 if i == 0 else 0.0 for i in range(DIM)] for _ in texts]


class FakeRerank:
    async def rerank(self, query, documents, top_n, model=None):
        return [0.5 + 0.1 * i for i in range(len(documents))]


async def _unique_user(make_user, is_superuser=False):
    return await make_user(f"u-{uuid.uuid4().hex[:8]}", "password", is_superuser=is_superuser)


async def _role_dataset(make_user, db_session):
    owner = await _unique_user(make_user)
    editor = await _unique_user(make_user)
    viewer = await _unique_user(make_user)
    outsider = await _unique_user(make_user)
    ds = await DatasetService(db_session).create(user=owner, name="ds", description="")
    await DatasetMemberRepository(db_session).create(ds.id, editor.id, "editor")
    await DatasetMemberRepository(db_session).create(ds.id, viewer.id, "viewer")
    await db_session.commit()
    return ds, owner, editor, viewer, outsider


async def _auth_headers(user):
    settings = get_settings()
    token = create_access_token(str(user.id), settings)
    return {"Authorization": f"Bearer {token}"}


async def _client(api_app, user):
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api_app),
        base_url="http://test",
        headers=await _auth_headers(user),
    )


async def test_dataset_create_adds_owner_member(api_app, db_session, make_user):
    user = await _unique_user(make_user)
    async with await _client(api_app, user) as c:
        resp = await c.post("/api/core/dataset/create", json={"name": "new"})
    assert resp.status_code == 200
    dataset_id = resp.json()["id"]
    member = await DatasetMemberRepository(db_session).get_valid(dataset_id, user.id)
    assert member is not None and member.role == "owner"


async def test_dataset_detail_has_my_role(api_app, db_session, make_user):
    owner = await _unique_user(make_user)
    ds = await DatasetService(db_session).create(user=owner, name="owned", description="")
    await db_session.commit()
    async with await _client(api_app, owner) as c:
        resp = await c.get("/api/core/dataset/detail", params={"id": str(ds.id)})
    assert resp.status_code == 200
    assert resp.json()["myRole"] == "owner"


async def test_list_filters_for_non_superuser(api_app, db_session, make_user):
    owner = await _unique_user(make_user)
    other = await _unique_user(make_user)
    ds = await DatasetService(db_session).create(user=owner, name="owner-ds", description="")
    await db_session.commit()

    async with await _client(api_app, owner) as c:
        resp = await c.get("/api/core/dataset/list")
    assert resp.status_code == 200
    assert any(d["id"] == str(ds.id) for d in resp.json())

    async with await _client(api_app, other) as c:
        resp = await c.get("/api/core/dataset/list")
    assert resp.status_code == 200
    assert not any(d["id"] == str(ds.id) for d in resp.json())


async def test_members_crud(api_app, db_session, make_user):
    ds, owner, editor, viewer, _ = await _role_dataset(make_user, db_session)
    async with await _client(api_app, owner) as c:
        resp = await c.get(f"/api/core/dataset/{ds.id}/members")
        assert resp.status_code == 200
        members = {int(m["userId"]): m["role"] for m in resp.json()}
        assert members[owner.id] == "owner"
        assert members[editor.id] == "editor"
        assert members[viewer.id] == "viewer"

        new_user = await _unique_user(make_user)
        resp = await c.post(f"/api/core/dataset/{ds.id}/members", json={"username": new_user.username, "role": "editor"})
        assert resp.status_code == 200

        resp = await c.patch(f"/api/core/dataset/{ds.id}/members/{new_user.id}", json={"role": "viewer"})
        assert resp.status_code == 200

        resp = await c.delete(f"/api/core/dataset/{ds.id}/members/{new_user.id}")
        assert resp.status_code == 200

        resp = await c.get(f"/api/core/dataset/{ds.id}/members")
        assert new_user.id not in {int(m["userId"]) for m in resp.json()}


async def test_last_owner_remove_protected(api_app, db_session, make_user):
    owner = await _unique_user(make_user)
    ds = await DatasetService(db_session).create(user=owner, name="ds", description="")
    await db_session.commit()
    async with await _client(api_app, owner) as c:
        resp = await c.delete(f"/api/core/dataset/{ds.id}/members/{owner.id}")
    assert resp.status_code == 422
    assert "last owner" in resp.json()["detail"].lower()


async def test_last_owner_demote_protected(api_app, db_session, make_user):
    owner = await _unique_user(make_user)
    ds = await DatasetService(db_session).create(user=owner, name="ds", description="")
    await db_session.commit()
    async with await _client(api_app, owner) as c:
        resp = await c.patch(f"/api/core/dataset/{ds.id}/members/{owner.id}", json={"role": "editor"})
    assert resp.status_code == 422
    assert "last owner" in resp.json()["detail"].lower()


async def test_viewer_cannot_write_data(api_app, db_session, make_user):
    ds, _owner, _editor, viewer, _ = await _role_dataset(make_user, db_session)
    col = await CollectionService(db_session).create(dataset_id=ds.id, parent_id=None, name="c", type="virtual")
    await db_session.commit()

    async with await _client(api_app, viewer) as c:
        resp = await c.post("/api/core/dataset/data/pushData", json={"collectionId": str(col.id), "data": [{"q": "x"}]})
        assert resp.status_code == 403
        assert resp.json()["detail"] == "permission denied"

        resp = await c.put("/api/core/dataset/collection/update", json={"id": str(col.id), "name": "x"})
        assert resp.status_code == 403


async def test_editor_cannot_manage_members(api_app, db_session, make_user):
    ds, _owner, editor, _, _ = await _role_dataset(make_user, db_session)
    await db_session.commit()
    async with await _client(api_app, editor) as c:
        resp = await c.get(f"/api/core/dataset/{ds.id}/members")
        assert resp.status_code == 200
        resp = await c.post(f"/api/core/dataset/{ds.id}/members", json={"username": "x", "role": "viewer"})
        assert resp.status_code == 403


async def test_outsider_cannot_access_dataset(api_app, db_session, make_user):
    ds, _, _, _, outsider = await _role_dataset(make_user, db_session)
    await db_session.commit()
    async with await _client(api_app, outsider) as c:
        resp = await c.get("/api/core/dataset/detail", params={"id": str(ds.id)})
    assert resp.status_code == 403


async def test_outsider_cannot_search(api_app, db_session, make_user):
    ds, _, _, _, outsider = await _role_dataset(make_user, db_session)
    await db_session.commit()

    api_app.dependency_overrides[get_embedding] = lambda: FakeEmbedding()
    api_app.dependency_overrides[get_rerank] = lambda: FakeRerank()
    async with await _client(api_app, outsider) as c:
        resp = await c.post("/api/core/dataset/search", json={"datasetId": str(ds.id), "text": "x"})
    assert resp.status_code == 403


async def test_collection_cross_dataset_422(api_app, db_session, make_user):
    owner = await _unique_user(make_user)
    ds1 = await DatasetService(db_session).create(user=owner, name="ds1", description="")
    ds2 = await DatasetService(db_session).create(user=owner, name="ds2", description="")
    col1 = await CollectionService(db_session).create(dataset_id=ds1.id, parent_id=None, name="c1", type="virtual")
    col2 = await CollectionService(db_session).create(dataset_id=ds2.id, parent_id=None, name="c2", type="virtual")
    await db_session.commit()
    async with await _client(api_app, owner) as c:
        resp = await c.request(
            "DELETE", "/api/core/dataset/collection/delete", json={"collectionIds": [str(col1.id), str(col2.id)]}
        )
    assert resp.status_code == 422


async def test_users_management_requires_superuser(api_app, db_session, make_user):
    normal = await _unique_user(make_user)
    async with await _client(api_app, normal) as c:
        resp = await c.get("/api/users/")
    assert resp.status_code == 403


async def test_users_self_modify_422(api_app, db_session, make_user):
    admin = await _unique_user(make_user, is_superuser=True)
    async with await _client(api_app, admin) as c:
        resp = await c.patch(f"/api/users/{admin.id}", json={"isActive": False})
    assert resp.status_code == 422


async def test_superuser_list_sees_all(api_app, db_session, make_user):
    owner = await _unique_user(make_user)
    ds = await DatasetService(db_session).create(user=owner, name="super-ds", description="")
    admin = await _unique_user(make_user, is_superuser=True)
    await db_session.commit()
    async with await _client(api_app, admin) as c:
        resp = await c.get("/api/core/dataset/list")
    assert resp.status_code == 200
    assert any(d["id"] == str(ds.id) for d in resp.json())


async def test_superuser_detail_my_role_owner(api_app, db_session, make_user):
    owner = await _unique_user(make_user)
    ds = await DatasetService(db_session).create(user=owner, name="super-ds", description="")
    admin = await _unique_user(make_user, is_superuser=True)
    await db_session.commit()
    async with await _client(api_app, admin) as c:
        resp = await c.get("/api/core/dataset/detail", params={"id": str(ds.id)})
    assert resp.status_code == 200
    assert resp.json()["myRole"] == "owner"


async def test_collection_data_access_by_collection_id(api_app, db_session, make_user):
    ds, _owner, editor, viewer, _ = await _role_dataset(make_user, db_session)
    col = await CollectionService(db_session).create(dataset_id=ds.id, parent_id=None, name="c", type="virtual")
    await db_session.commit()

    async with await _client(api_app, viewer) as c:
        resp = await c.get("/api/core/dataset/collection/detail", params={"id": str(col.id)})
        assert resp.status_code == 200
        resp = await c.get("/api/core/dataset/data/list", params={"collectionId": str(col.id)})
        assert resp.status_code == 200

    async with await _client(api_app, editor) as c:
        resp = await c.post("/api/core/dataset/data/pushData", json={"collectionId": str(col.id), "data": [{"q": "x"}]})
        assert resp.status_code == 200
        assert resp.json() == {"insertLen": 1}

    async with await _client(api_app, viewer) as c:
        resp = await c.get("/api/core/dataset/data/list", params={"collectionId": str(col.id)})
        data_id = resp.json()["list"][0]["id"]
        resp = await c.get("/api/core/dataset/data/detail", params={"id": data_id})
        assert resp.status_code == 200

    async with await _client(api_app, editor) as c:
        resp = await c.put("/api/core/dataset/data/update", json={"dataId": data_id, "q": "y"})
        assert resp.status_code == 200
        resp = await c.delete("/api/core/dataset/data/delete", params={"id": data_id})
        assert resp.status_code == 200


async def test_viewer_cannot_update_dataset_settings(api_app, db_session, make_user):
    ds, _owner, editor, viewer, _ = await _role_dataset(make_user, db_session)
    await db_session.commit()
    async with await _client(api_app, viewer) as c:
        resp = await c.put("/api/core/dataset/update", json={"id": str(ds.id), "name": "x"})
    assert resp.status_code == 403

    async with await _client(api_app, editor) as c:
        resp = await c.put("/api/core/dataset/update", json={"id": str(ds.id), "name": "x"})
    assert resp.status_code == 200


async def test_owner_can_delete_dataset(api_app, db_session, make_user):
    ds, owner, editor, _, _ = await _role_dataset(make_user, db_session)
    await db_session.commit()
    async with await _client(api_app, editor) as c:
        resp = await c.delete("/api/core/dataset/delete", params={"id": str(ds.id)})
    assert resp.status_code == 403

    async with await _client(api_app, owner) as c:
        resp = await c.delete("/api/core/dataset/delete", params={"id": str(ds.id)})
    assert resp.status_code == 200


async def test_users_list_and_update(api_app, db_session, make_user):
    admin = await _unique_user(make_user, is_superuser=True)
    target = await _unique_user(make_user)
    async with await _client(api_app, admin) as c:
        resp = await c.get("/api/users/", params={"offset": 0, "pageSize": 100})
    assert resp.status_code == 200
    body = resp.json()
    assert any(u["id"] == target.id for u in body["list"])

    async with await _client(api_app, admin) as c:
        resp = await c.patch(f"/api/users/{target.id}", json={"isActive": False})
    assert resp.status_code == 200
    assert resp.json()["isActive"] is False

    async with await _client(api_app, target) as c:
        resp = await c.post("/api/auth/login", json={"username": target.username, "password": "password"})
    assert resp.status_code == 401
