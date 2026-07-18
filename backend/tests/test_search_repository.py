from tests.conftest import requires_db
from vector_match.repositories.collections import CollectionRepository
from vector_match.repositories.data import DataRepository
from vector_match.repositories.datasets import DatasetRepository
from vector_match.repositories.search import SearchRepository

pytestmark = requires_db

DIM = 1024


def _unit_vec(i: int) -> list[float]:
    v = [0.0] * DIM
    v[i] = 1.0
    return v


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
    return r1, r2


async def test_vector_recall_orders_by_distance(db_session):
    r1, r2 = await _fixture(db_session)
    repo = SearchRepository(db_session)
    hits = await repo.vector_recall(r1.dataset_id, _unit_vec(0), limit=10)
    assert hits[0][0] == r1.id
    assert hits[0][1] < 1e-6
    assert hits[1][0] == r2.id


async def test_vector_recall_skips_untrained_and_deleted(db_session):
    r1, r2 = await _fixture(db_session)
    repo = SearchRepository(db_session)
    data_repo = DataRepository(db_session)
    await data_repo.soft_delete_many([r2.id])
    hits = await repo.vector_recall(r1.dataset_id, _unit_vec(1), limit=10)
    assert [h[0] for h in hits] == [r1.id]


async def test_fts_recall(db_session):
    r1, _ = await _fixture(db_session)
    repo = SearchRepository(db_session)
    hits = await repo.fts_recall(r1.dataset_id, "蓝筹", limit=10)
    assert [h[0] for h in hits] == [r1.id]
    hits = await repo.fts_recall(r1.dataset_id, "混合", limit=10)
    assert len(hits) == 2  # 两条都含「混合」


async def test_hydrate_returns_source_name(db_session):
    r1, r2 = await _fixture(db_session)
    repo = SearchRepository(db_session)
    rows = await repo.hydrate([r1.id, r2.id])
    by_id = {r.id: r for r in rows}
    assert by_id[r1.id].source_name == "基金集"
    assert by_id[r2.id].a == "003095"
