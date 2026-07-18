from tests.conftest import requires_db

pytestmark = requires_db


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200 and resp.json() == {"status": "ok"}


async def test_auth_required(client):
    resp = await client.get("/api/core/dataset/list", headers={"Authorization": ""})
    assert resp.status_code == 401
    resp = await client.get("/api/core/dataset/list", headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401


async def test_dataset_crud_flow(client):
    resp = await client.post("/api/core/dataset/create", json={"name": "基金库", "description": "fund"})
    assert resp.status_code == 200
    dataset_id = resp.json()["id"]

    resp = await client.get("/api/core/dataset/list")
    assert any(d["id"] == dataset_id for d in resp.json())
    assert "vectorModel" in resp.json()[0]  # 对外驼峰

    resp = await client.get("/api/core/dataset/detail", params={"id": dataset_id})
    assert resp.json()["name"] == "基金库"

    resp = await client.put("/api/core/dataset/update", json={"id": dataset_id, "name": "基金库2"})
    assert resp.status_code == 200
    resp = await client.get("/api/core/dataset/detail", params={"id": dataset_id})
    assert resp.json()["name"] == "基金库2"

    resp = await client.delete("/api/core/dataset/delete", params={"id": dataset_id})
    assert resp.status_code == 200
    resp = await client.get("/api/core/dataset/detail", params={"id": dataset_id})
    assert resp.status_code == 404
    assert "detail" in resp.json()
