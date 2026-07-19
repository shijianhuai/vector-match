import httpx
import pytest_asyncio

from tests.conftest import requires_db
from vector_match.api.deps import get_embedding, get_rerank
from vector_match.repositories.data import DataRepository
from vector_match.services.collections import CollectionService
from vector_match.services.datasets import DatasetService

pytestmark = requires_db

DIM = 1024


def _unit_vec(i: int) -> list[float]:
    v = [0.0] * DIM
    v[i] = 1.0
    return v


class FakeEmbedding:
    async def embed(self, texts):
        return [_unit_vec(0) for _ in texts]


class FakeRerank:
    async def rerank(self, query, documents, top_n, model=None):
        return [0.5 + 0.1 * i for i in range(len(documents))]


@pytest_asyncio.fixture
async def client(api_app, db_session):
    ds = await DatasetService(db_session).create(name="d", description="")
    col = await CollectionService(db_session).create(dataset_id=ds.id, parent_id=None, name="基金集", type="virtual")
    repo = DataRepository(db_session)
    r1, r2 = await repo.create_many(
        [
            {"dataset_id": ds.id, "collection_id": col.id, "q": "易方达蓝筹精选混合", "a": "005827"},
            {"dataset_id": ds.id, "collection_id": col.id, "q": "中欧医疗健康混合", "a": "003095"},
        ]
    )
    i1 = await repo.add_index(r1.id, "易方达蓝筹精选混合", type="default")
    i2 = await repo.add_index(r2.id, "中欧医疗健康混合", type="default")
    await repo.set_index_vector(i1.id, _unit_vec(0))
    await repo.set_index_vector(i2.id, _unit_vec(1))
    await repo.set_full_text_tokens(r1.id, "易方达 蓝筹 精选 混合")
    await repo.set_full_text_tokens(r2.id, "中欧 医疗 健康 混合")

    api_app.dependency_overrides[get_embedding] = lambda: FakeEmbedding()
    api_app.dependency_overrides[get_rerank] = lambda: FakeRerank()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api_app),
        base_url="http://test",
        headers={"Authorization": "Bearer dev-key"},
    ) as c:
        c.dataset_id = str(ds.id)
        c.r1_id = str(r1.id)
        yield c


async def test_search_embedding(client):
    resp = await client.post(
        "/api/core/dataset/search",
        json={"datasetId": client.dataset_id, "text": "蓝筹", "searchMode": "embedding"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["id"] == client.r1_id
    assert body[0]["sourceName"] == "基金集"
    assert body[0]["score"] > 0.99


async def test_search_fulltext(client):
    resp = await client.post(
        "/api/core/dataset/search",
        json={"datasetId": client.dataset_id, "text": "蓝筹", "searchMode": "fullTextRecall"},
    )
    assert resp.json()[0]["id"] == client.r1_id


async def test_search_mixed_with_rerank(client):
    resp = await client.post(
        "/api/core/dataset/search",
        json={
            "datasetId": client.dataset_id,
            "text": "蓝筹",
            "searchMode": "mixedRecall",
            "usingReRank": True,
            "topK": 5,
        },
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_search_missing_dataset_404(client):
    from uuid import uuid4

    resp = await client.post("/api/core/dataset/search", json={"datasetId": str(uuid4()), "text": "x"})
    assert resp.status_code == 404
