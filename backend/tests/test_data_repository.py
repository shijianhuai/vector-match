from tests.conftest import requires_db
from vector_match.repositories.collections import CollectionRepository
from vector_match.repositories.data import DataRepository
from vector_match.repositories.datasets import DatasetRepository

pytestmark = requires_db


async def _make_collection(db_session):
    ds = await DatasetRepository(db_session).create(name="d", description="", vector_model="m")
    return await CollectionRepository(db_session).create(dataset_id=ds.id, parent_id=None, name="c", type="virtual")


async def test_create_many_and_get(db_session):
    col = await _make_collection(db_session)
    repo = DataRepository(db_session)
    rows = await repo.create_many(
        [
            {"dataset_id": col.dataset_id, "collection_id": col.id, "q": "易方达蓝筹精选混合", "a": "005827"},
            {"dataset_id": col.dataset_id, "collection_id": col.id, "q": "中欧医疗健康混合", "a": "003095"},
        ]
    )
    assert len(rows) == 2
    got = await repo.get(rows[0].id)
    assert got.q == "易方达蓝筹精选混合" and got.full_text_tokens == ""


async def test_index_lifecycle(db_session):
    col = await _make_collection(db_session)
    repo = DataRepository(db_session)
    (row,) = await repo.create_many([{"dataset_id": col.dataset_id, "collection_id": col.id, "q": "q1", "a": None}])
    await repo.add_index(row.id, "q1", type="default")
    await repo.add_index(row.id, "别名1")

    untrained = await repo.list_valid_indexes(row.id, only_untrained=True)
    assert len(untrained) == 2

    await repo.set_index_vector(untrained[0].id, [0.0] * 1024)
    assert len(await repo.list_valid_indexes(row.id, only_untrained=True)) == 1
    assert await repo.list_trained_data_ids([row.id]) == {row.id}

    await repo.invalidate_indexes(row.id)
    assert await repo.list_valid_indexes(row.id) == []
    assert await repo.list_trained_data_ids([row.id]) == set()


async def test_list_page_search_and_soft_delete(db_session):
    col = await _make_collection(db_session)
    repo = DataRepository(db_session)
    rows = await repo.create_many(
        [
            {"dataset_id": col.dataset_id, "collection_id": col.id, "q": "基金甲", "a": "001"},
            {"dataset_id": col.dataset_id, "collection_id": col.id, "q": "基金乙", "a": "002"},
        ]
    )
    items, total = await repo.list_page(col.id, offset=0, page_size=10, search_text="基金甲")
    assert total == 1 and items[0].q == "基金甲"
    await repo.soft_delete_many([rows[0].id])
    assert await repo.get(rows[0].id) is None
    _, total = await repo.list_page(col.id, offset=0, page_size=10, search_text=None)
    assert total == 1


async def test_update_fields_and_tokens(db_session):
    col = await _make_collection(db_session)
    repo = DataRepository(db_session)
    (row,) = await repo.create_many([{"dataset_id": col.dataset_id, "collection_id": col.id, "q": "旧", "a": None}])
    await repo.update_fields(row.id, q="新", a="代码")
    await repo.set_full_text_tokens(row.id, "新 代码")
    got = await repo.get(row.id)
    assert got.q == "新" and got.a == "代码" and got.full_text_tokens == "新 代码"
