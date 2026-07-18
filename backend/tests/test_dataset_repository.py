from tests.conftest import requires_db
from vector_match.repositories.datasets import DatasetRepository

pytestmark = requires_db


async def test_create_get_list(db_session):
    repo = DatasetRepository(db_session)
    ds = await repo.create(name="基金库", description="fund", vector_model="m")
    assert ds.id is not None
    got = await repo.get(ds.id)
    assert got.name == "基金库"
    assert ds in await repo.list()


async def test_update_and_soft_delete(db_session):
    repo = DatasetRepository(db_session)
    ds = await repo.create(name="a", description="", vector_model="m")
    await repo.update(ds.id, name="b")
    assert (await repo.get(ds.id)).name == "b"
    await repo.soft_delete(ds.id)
    assert await repo.get(ds.id) is None
