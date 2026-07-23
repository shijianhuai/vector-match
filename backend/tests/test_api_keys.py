from tests.conftest import requires_db
from vector_match.core.config import get_settings
from vector_match.core.security import create_access_token

pytestmark = requires_db


async def _jwt_headers(user):
    return {"Authorization": f"Bearer {create_access_token(str(user.id), get_settings())}"}


async def test_normal_user_default_no_permission(client, make_user):
    user = await make_user("apikey-normal-no-perm")
    headers = await _jwt_headers(user)
    get_resp = await client.get("/api/api-keys/", headers=headers)
    assert get_resp.status_code == 403
    post_resp = await client.post("/api/api-keys/", json={"name": "should fail"}, headers=headers)
    assert post_resp.status_code == 403


async def test_superuser_unrestricted(client, make_user):
    user = await make_user("apikey-superuser", is_superuser=True)
    headers = await _jwt_headers(user)
    resp = await client.post("/api/api-keys/", json={"name": "super key"}, headers=headers)
    assert resp.status_code == 200
    list_resp = await client.get("/api/api-keys/", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1


async def test_allow_api_key_enabled_by_superuser(client, make_user):
    user = await make_user("apikey-normal-enabled")
    headers = await _jwt_headers(user)
    enable_resp = await client.patch(f"/api/users/{user.id}", json={"allowApiKey": True})
    assert enable_resp.status_code == 200
    assert enable_resp.json()["allowApiKey"] is True
    resp = await client.post("/api/api-keys/", json={"name": "enabled key"}, headers=headers)
    assert resp.status_code == 200


async def test_create_api_key_format(client, make_user):
    user = await make_user("apikey-format", allow_api_key=True)
    headers = await _jwt_headers(user)
    resp = await client.post("/api/api-keys/", json={"name": "test key"}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["key"].startswith("sk-")
    assert len(data["key"]) == 35
    assert data["name"] == "test key"
    assert "createTime" in data
    assert "lastUsedAt" in data


async def test_create_api_key_validation(client, make_user):
    user = await make_user("apikey-validation", allow_api_key=True)
    headers = await _jwt_headers(user)
    r1 = await client.post("/api/api-keys/", json={"name": ""}, headers=headers)
    assert r1.status_code == 422
    r2 = await client.post("/api/api-keys/", json={"name": "x" * 129}, headers=headers)
    assert r2.status_code == 422


async def test_list_only_own_keys(client, make_user):
    user1 = await make_user("apikey-owner1", allow_api_key=True)
    user2 = await make_user("apikey-owner2", allow_api_key=True)
    h1 = await _jwt_headers(user1)
    h2 = await _jwt_headers(user2)
    await client.post("/api/api-keys/", json={"name": "u1 key"}, headers=h1)
    await client.post("/api/api-keys/", json={"name": "u2 key"}, headers=h2)
    list1 = await client.get("/api/api-keys/", headers=h1)
    assert list1.status_code == 200
    assert list1.json()["total"] == 1
    assert list1.json()["list"][0]["name"] == "u1 key"
    list2 = await client.get("/api/api-keys/", headers=h2)
    assert list2.json()["total"] == 1
    assert list2.json()["list"][0]["name"] == "u2 key"


async def test_update_key(client, make_user):
    user1 = await make_user("apikey-update1", allow_api_key=True)
    user2 = await make_user("apikey-update2", allow_api_key=True)
    h1 = await _jwt_headers(user1)
    h2 = await _jwt_headers(user2)
    create_resp = await client.post("/api/api-keys/", json={"name": "old name"}, headers=h1)
    key_id = create_resp.json()["id"]
    patch_resp = await client.patch(f"/api/api-keys/{key_id}", json={"name": "new name"}, headers=h1)
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "new name"
    other_patch = await client.patch(f"/api/api-keys/{key_id}", json={"name": "hacked"}, headers=h2)
    assert other_patch.status_code == 404


async def test_delete_key(client, make_user):
    user = await make_user("apikey-delete", allow_api_key=True)
    h = await _jwt_headers(user)
    create_resp = await client.post("/api/api-keys/", json={"name": "to delete"}, headers=h)
    key_id = create_resp.json()["id"]
    delete_resp = await client.delete(f"/api/api-keys/{key_id}", headers=h)
    assert delete_resp.status_code == 200
    list_resp = await client.get("/api/api-keys/", headers=h)
    assert list_resp.json()["total"] == 0


async def test_delete_other_user_key(client, make_user):
    user1 = await make_user("apikey-del1", allow_api_key=True)
    user2 = await make_user("apikey-del2", allow_api_key=True)
    h1 = await _jwt_headers(user1)
    h2 = await _jwt_headers(user2)
    create_resp = await client.post("/api/api-keys/", json={"name": "owned"}, headers=h1)
    key_id = create_resp.json()["id"]
    delete_resp = await client.delete(f"/api/api-keys/{key_id}", headers=h2)
    assert delete_resp.status_code == 404


async def test_auth_with_api_key(client, make_user):
    user = await make_user("apikey-auth", allow_api_key=True)
    h_jwt = await _jwt_headers(user)
    create_resp = await client.post("/api/api-keys/", json={"name": "auth key"}, headers=h_jwt)
    sk = create_resp.json()["key"]
    h_sk = {"Authorization": f"Bearer {sk}"}
    me_resp = await client.get("/api/auth/me", headers=h_sk)
    assert me_resp.status_code == 200
    assert me_resp.json()["id"] == user.id


async def test_auth_with_fake_key(client):
    headers = {"Authorization": "Bearer sk-00000000000000000000000000000000"}
    me_resp = await client.get("/api/auth/me", headers=headers)
    assert me_resp.status_code == 401


async def test_last_used_at_updated_on_sk_auth(client, make_user):
    user = await make_user("apikey-last-used", allow_api_key=True)
    h_jwt = await _jwt_headers(user)
    create_resp = await client.post("/api/api-keys/", json={"name": "usage key"}, headers=h_jwt)
    sk = create_resp.json()["key"]
    assert create_resp.json()["lastUsedAt"] is None
    me_resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {sk}"})
    assert me_resp.status_code == 200
    list_resp = await client.get("/api/api-keys/", headers=h_jwt)
    assert list_resp.status_code == 200
    target = next(k for k in list_resp.json()["list"] if k["key"] == sk)
    assert target["lastUsedAt"] is not None


async def test_auth_with_deleted_key(client, make_user):
    user = await make_user("apikey-deleted", allow_api_key=True)
    h_jwt = await _jwt_headers(user)
    create_resp = await client.post("/api/api-keys/", json={"name": "deleted key"}, headers=h_jwt)
    key_id = create_resp.json()["id"]
    sk = create_resp.json()["key"]
    await client.delete(f"/api/api-keys/{key_id}", headers=h_jwt)
    h_sk = {"Authorization": f"Bearer {sk}"}
    me_resp = await client.get("/api/auth/me", headers=h_sk)
    assert me_resp.status_code == 401


async def test_user_response_contains_allow_api_key(client, make_user):
    user = await make_user("apikey-allow-field")
    enable_resp = await client.patch(f"/api/users/{user.id}", json={"allowApiKey": True})
    assert enable_resp.status_code == 200
    assert "allowApiKey" in enable_resp.json()
    assert enable_resp.json()["allowApiKey"] is True

    me_headers = await _jwt_headers(user)
    me_resp = await client.get("/api/auth/me", headers=me_headers)
    assert me_resp.status_code == 200
    assert "allowApiKey" in me_resp.json()
    assert me_resp.json()["allowApiKey"] is True

    list_resp = await client.get("/api/users/")
    assert list_resp.status_code == 200
    users = list_resp.json()["list"]
    target = next((u for u in users if u["id"] == user.id), None)
    assert target is not None
    assert target["allowApiKey"] is True
