import pytest

from tests.conftest import requires_db
from vector_match.core.config import Settings
from vector_match.core.exceptions import NotFoundError, ProviderConfigError, ValidationError
from vector_match.repositories.collections import CollectionRepository
from vector_match.repositories.data import DataRepository
from vector_match.repositories.datasets import DatasetRepository
from vector_match.services.search import SearchParams, SearchService

pytestmark = requires_db

DIM = 1024


def _unit_vec(i: int) -> list[float]:
    v = [0.0] * DIM
    v[i] = 1.0
    return v


class FakeEmbedding:
    def __init__(self, vector):
        self._vector = vector

    async def embed(self, texts):
        return [self._vector for _ in texts]


class FakeRerank:
    def __init__(self, scores):
        self._scores = scores

    async def rerank(self, query, documents, top_n, model=None):
        return self._scores[: len(documents)]


async def _fixture(db_session):
    ds = await DatasetRepository(db_session).create(name="d", description="", vector_model="m")
    col = await CollectionRepository(db_session).create(dataset_id=ds.id, parent_id=None, name="基金集", type="virtual")
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
    return ds, r1, r2


def _params(ds, **kw):
    defaults = {"dataset_id": ds.id, "text": "蓝筹"}
    defaults.update(kw)
    return SearchParams(**defaults)


async def test_embedding_mode(db_session):
    ds, r1, _ = await _fixture(db_session)
    svc = SearchService(db_session, FakeEmbedding(_unit_vec(0)), None, Settings())
    hits = await svc.search(_params(ds, search_mode="embedding"))
    assert hits[0].id == r1.id
    assert hits[0].score == pytest.approx(1.0, abs=1e-6)
    assert hits[0].source_name == "基金集"


async def test_embedding_similarity_filter(db_session):
    ds, r1, _ = await _fixture(db_session)
    svc = SearchService(db_session, FakeEmbedding(_unit_vec(0)), None, Settings())
    hits = await svc.search(_params(ds, search_mode="embedding", similarity=0.5))
    assert [h.id for h in hits] == [r1.id]  # r2 得分约 0 被过滤


async def test_fulltext_mode(db_session):
    ds, r1, _ = await _fixture(db_session)
    svc = SearchService(db_session, FakeEmbedding(_unit_vec(0)), None, Settings())
    hits = await svc.search(_params(ds, text="蓝筹", search_mode="fullTextRecall"))
    assert hits[0].id == r1.id


async def test_mixed_mode_fuses(db_session):
    ds, r1, _ = await _fixture(db_session)
    svc = SearchService(db_session, FakeEmbedding(_unit_vec(0)), None, Settings())
    hits = await svc.search(_params(ds, search_mode="mixedRecall"))
    assert hits[0].id == r1.id
    assert len(hits) == 2


async def test_rerank_reorders(db_session):
    ds, _, r2 = await _fixture(db_session)
    svc = SearchService(db_session, FakeEmbedding(_unit_vec(0)), FakeRerank([0.1, 0.9]), Settings())
    hits = await svc.search(_params(ds, search_mode="embedding", using_re_rank=True))
    assert hits[0].id == r2.id and hits[0].score == pytest.approx(0.9)


async def test_validations(db_session):
    ds, _, _ = await _fixture(db_session)
    svc = SearchService(db_session, FakeEmbedding(_unit_vec(0)), None, Settings())
    with pytest.raises(ValidationError):
        await svc.search(_params(ds, text="  "))
    with pytest.raises(ValidationError):
        await svc.search(_params(ds, search_mode="bad"))
    with pytest.raises(ProviderConfigError):
        await svc.search(_params(ds, using_re_rank=True))
    with pytest.raises(NotFoundError):
        from uuid import uuid4

        await svc.search(_params(ds, dataset_id=uuid4()))
