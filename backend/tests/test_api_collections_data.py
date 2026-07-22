from tests.conftest import requires_db

pytestmark = requires_db


async def _make_dataset(client) -> str:
    resp = await client.post("/api/core/dataset/create", json={"name": "d"})
    return resp.json()["id"]


async def test_collection_flow(client):
    dataset_id = await _make_dataset(client)
    resp = await client.post(
        "/api/core/dataset/collection/create",
        json={"datasetId": dataset_id, "name": "手动集", "type": "virtual"},
    )
    assert resp.status_code == 200
    collection_id = resp.json()["id"]

    resp = await client.get(
        "/api/core/dataset/collection/list",
        params={"datasetId": dataset_id, "pageSize": 10, "offset": 0},
    )
    body = resp.json()
    assert body["total"] == 1 and body["list"][0]["id"] == collection_id
    assert body["list"][0]["datasetId"] == dataset_id  # 驼峰

    resp = await client.get("/api/core/dataset/collection/detail", params={"id": collection_id})
    assert resp.json()["name"] == "手动集"

    resp = await client.put("/api/core/dataset/collection/update", json={"id": collection_id, "name": "手动集2"})
    assert resp.status_code == 200

    resp = await client.request(
        "DELETE", "/api/core/dataset/collection/delete", json={"collectionIds": [collection_id]}
    )
    assert resp.status_code == 200
    resp = await client.get("/api/core/dataset/collection/detail", params={"id": collection_id})
    assert resp.status_code == 404


async def test_data_flow(client):
    dataset_id = await _make_dataset(client)
    resp = await client.post(
        "/api/core/dataset/collection/create",
        json={"datasetId": dataset_id, "name": "c", "type": "virtual"},
    )
    collection_id = resp.json()["id"]

    resp = await client.post(
        "/api/core/dataset/data/pushData",
        json={
            "collectionId": collection_id,
            "data": [
                {"q": "易方达蓝筹精选混合", "a": "005827", "indexes": [{"text": "易方达蓝筹"}]},
                {"q": "中欧医疗健康混合A", "a": "003095"},
            ],
        },
    )
    assert resp.status_code == 200 and resp.json() == {"insertLen": 2, "updateLen": 0, "skipLen": 0}

    resp = await client.get("/api/core/dataset/data/list", params={"collectionId": collection_id})
    body = resp.json()
    assert body["total"] == 2
    assert body["list"][0]["trained"] is False
    data_id = body["list"][0]["id"]

    resp = await client.get("/api/core/dataset/data/detail", params={"id": data_id})
    assert "indexes" in resp.json() and "trained" in resp.json()

    resp = await client.put("/api/core/dataset/data/update", json={"dataId": data_id, "q": "改名后的基金"})
    assert resp.status_code == 200
    resp = await client.get("/api/core/dataset/data/detail", params={"id": data_id})
    assert resp.json()["q"] == "改名后的基金"

    resp = await client.delete("/api/core/dataset/data/delete", params={"id": data_id})
    assert resp.status_code == 200
    resp = await client.get("/api/core/dataset/data/detail", params={"id": data_id})
    assert resp.status_code == 404


async def test_push_to_missing_collection_404(client):
    from uuid import uuid4

    resp = await client.post(
        "/api/core/dataset/data/pushData",
        json={"collectionId": str(uuid4()), "data": [{"q": "x"}]},
    )
    assert resp.status_code == 404


async def test_push_updatetime_without_key_id_422(client):
    dataset_id = await _make_dataset(client)
    resp = await client.post(
        "/api/core/dataset/collection/create",
        json={"datasetId": dataset_id, "name": "c", "type": "virtual"},
    )
    collection_id = resp.json()["id"]
    resp = await client.post(
        "/api/core/dataset/data/pushData",
        json={"collectionId": collection_id, "data": [{"q": "x", "updatetime": "2026-07-22T12:00:00Z"}]},
    )
    assert resp.status_code == 422


async def test_push_duplicate_key_id_422(client):
    dataset_id = await _make_dataset(client)
    resp = await client.post(
        "/api/core/dataset/collection/create",
        json={"datasetId": dataset_id, "name": "c", "type": "virtual"},
    )
    collection_id = resp.json()["id"]
    resp = await client.post(
        "/api/core/dataset/data/pushData",
        json={
            "collectionId": collection_id,
            "data": [{"q": "a", "keyId": "k1"}, {"q": "b", "keyId": "k1"}],
        },
    )
    assert resp.status_code == 422


async def test_delete_by_key(client):
    dataset_id = await _make_dataset(client)
    resp = await client.post(
        "/api/core/dataset/collection/create",
        json={"datasetId": dataset_id, "name": "c", "type": "virtual"},
    )
    collection_id = resp.json()["id"]
    await client.post(
        "/api/core/dataset/data/pushData",
        json={"collectionId": collection_id, "data": [{"q": "a", "keyId": "k1"}, {"q": "b", "keyId": "k2"}]},
    )
    resp = await client.request(
        "DELETE",
        "/api/core/dataset/data/deleteByKey",
        json={"collectionId": collection_id, "keyIds": ["k1", "missing"]},
    )
    assert resp.status_code == 200
    assert resp.json() == {"deleteLen": 1}
    resp = await client.get("/api/core/dataset/data/list", params={"collectionId": collection_id})
    assert resp.json()["total"] == 1


async def test_push_with_key_id_and_list_detail(client):
    dataset_id = await _make_dataset(client)
    resp = await client.post(
        "/api/core/dataset/collection/create",
        json={"datasetId": dataset_id, "name": "c", "type": "virtual"},
    )
    collection_id = resp.json()["id"]
    await client.post(
        "/api/core/dataset/data/pushData",
        json={"collectionId": collection_id, "data": [{"q": "a", "keyId": "k1"}]},
    )
    resp = await client.get("/api/core/dataset/data/list", params={"collectionId": collection_id})
    data = resp.json()["list"][0]
    assert data["keyId"] == "k1"
    resp = await client.get("/api/core/dataset/data/detail", params={"id": data["id"]})
    assert resp.json()["keyId"] == "k1"
