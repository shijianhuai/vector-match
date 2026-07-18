from tests.conftest import requires_db
from vector_match.repositories.collections import CollectionRepository
from vector_match.repositories.datasets import DatasetRepository

pytestmark = requires_db


async def _make_dataset(db_session):
    return await DatasetRepository(db_session).create(name="d", description="", vector_model="m")


async def test_create_and_list_page(db_session):
    ds = await _make_dataset(db_session)
    repo = CollectionRepository(db_session)
    folder = await repo.create(dataset_id=ds.id, parent_id=None, name="目录", type="folder")
    c1 = await repo.create(dataset_id=ds.id, parent_id=folder.id, name="手动集A", type="virtual")
    await repo.create(dataset_id=ds.id, parent_id=folder.id, name="手动集B", type="virtual")

    items, total = await repo.list_page(ds.id, parent_id=folder.id, offset=0, page_size=10, search_text=None)
    assert total == 2 and len(items) == 2

    items, total = await repo.list_page(ds.id, parent_id=folder.id, offset=0, page_size=10, search_text="集A")
    assert total == 1 and items[0].id == c1.id


async def test_update_and_soft_delete_many(db_session):
    ds = await _make_dataset(db_session)
    repo = CollectionRepository(db_session)
    c1 = await repo.create(dataset_id=ds.id, parent_id=None, name="x", type="virtual")
    c2 = await repo.create(dataset_id=ds.id, parent_id=None, name="y", type="virtual")
    await repo.update(c1.id, name="x2")
    assert (await repo.get(c1.id)).name == "x2"
    await repo.soft_delete_many([c1.id, c2.id])
    assert await repo.get(c1.id) is None
    assert await repo.list_by_dataset(ds.id) == []
