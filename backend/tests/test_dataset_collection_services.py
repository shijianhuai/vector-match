from uuid import uuid4

import pytest

from tests.conftest import requires_db
from vector_match.core.exceptions import NotFoundError, ValidationError
from vector_match.repositories.collections import CollectionRepository
from vector_match.repositories.data import DataRepository
from vector_match.repositories.datasets import DatasetRepository
from vector_match.services.collections import CollectionService
from vector_match.services.datasets import DatasetService

pytestmark = requires_db


async def test_dataset_crud(db_session):
    svc = DatasetService(db_session)
    ds = await svc.create(name="基金库", description="d")
    assert (await svc.detail(ds.id)).name == "基金库"
    await svc.update(ds.id, name="基金库2")
    assert (await svc.detail(ds.id)).name == "基金库2"
    await svc.delete(ds.id)
    with pytest.raises(NotFoundError):
        await svc.detail(ds.id)


async def test_dataset_delete_cascades(db_session):
    ds_svc = DatasetService(db_session)
    ds = await ds_svc.create(name="d", description="")
    col = await CollectionService(db_session).create(dataset_id=ds.id, parent_id=None, name="c", type="virtual")
    data_repo = DataRepository(db_session)
    (row,) = await data_repo.create_many([{"dataset_id": ds.id, "collection_id": col.id, "q": "基金A", "a": "001"}])
    await data_repo.add_index(row.id, "基金A", type="default")

    await ds_svc.delete(ds.id)

    assert await DatasetRepository(db_session).get(ds.id) is None
    assert await CollectionRepository(db_session).get(col.id) is None
    assert await data_repo.get(row.id) is None
    assert await data_repo.list_valid_indexes(row.id) == []


async def test_collection_create_validations(db_session):
    svc = CollectionService(db_session)
    with pytest.raises(NotFoundError):
        await svc.create(dataset_id=uuid4(), parent_id=None, name="x", type="virtual")
    ds = await DatasetService(db_session).create(name="d", description="")
    with pytest.raises(ValidationError):
        await svc.create(dataset_id=ds.id, parent_id=None, name="x", type="bad-type")


async def test_collection_delete_cascades_to_children_and_data(db_session):
    ds = await DatasetService(db_session).create(name="d", description="")
    svc = CollectionService(db_session)
    folder = await svc.create(dataset_id=ds.id, parent_id=None, name="目录", type="folder")
    child = await svc.create(dataset_id=ds.id, parent_id=folder.id, name="子集", type="virtual")
    data_repo = DataRepository(db_session)
    (row,) = await data_repo.create_many([{"dataset_id": ds.id, "collection_id": child.id, "q": "基金B", "a": "002"}])

    await svc.delete([folder.id])

    assert await CollectionRepository(db_session).get(child.id) is None
    assert await data_repo.get(row.id) is None
