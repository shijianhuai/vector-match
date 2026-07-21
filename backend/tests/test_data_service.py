import pytest

from tests.conftest import requires_db
from vector_match.core.exceptions import NotFoundError, ValidationError
from vector_match.repositories.tasks import TaskRepository
from vector_match.services.collections import CollectionService
from vector_match.services.data import DataService, PushItem
from vector_match.services.datasets import DatasetService
from vector_match.services.users import UserService

pytestmark = requires_db


async def _make_virtual_collection(db_session, type="virtual"):
    from uuid import uuid4

    user = await UserService(db_session).create_user(username=f"testuser-{uuid4().hex[:8]}", password="password")
    ds = await DatasetService(db_session).create(user=user, name="d", description="")
    return await CollectionService(db_session).create(dataset_id=ds.id, parent_id=None, name="c", type=type)


async def test_push_creates_data_indexes_and_tasks(db_session):
    col = await _make_virtual_collection(db_session)
    svc = DataService(db_session)
    n = await svc.push(
        col.id,
        [
            PushItem(q="易方达蓝筹精选混合", a="005827", indexes=["易方达蓝筹", "蓝筹精选"]),
            PushItem(q="中欧医疗健康混合A", a="003095", indexes=[]),
        ],
    )
    assert n == 2
    items, total, trained = await svc.list_page(col.id, offset=0, page_size=10, search_text=None)
    assert total == 2 and trained == set()
    target = next(i for i in items if i.q == "易方达蓝筹精选混合")
    _data, indexes, is_trained = await svc.detail(target.id)
    assert is_trained is False
    assert {i.type for i in indexes} == {"default", "custom"}
    tasks = await TaskRepository(db_session).claim(10)
    assert len(tasks) == 2


async def test_push_validations(db_session):
    folder = await _make_virtual_collection(db_session, type="folder")
    svc = DataService(db_session)
    with pytest.raises(ValidationError):
        await svc.push(folder.id, [PushItem(q="x", a=None, indexes=[])])
    with pytest.raises(NotFoundError):
        from uuid import uuid4

        await svc.push(uuid4(), [PushItem(q="x", a=None, indexes=[])])
    col = await _make_virtual_collection(db_session)
    with pytest.raises(ValidationError):
        await svc.push(col.id, [PushItem(q="x", a=None, indexes=["a", "b", "c", "d", "e", "f"])])


async def test_update_rebuilds_indexes(db_session):
    col = await _make_virtual_collection(db_session)
    svc = DataService(db_session)
    await svc.push(col.id, [PushItem(q="旧名", a="001", indexes=["旧别名"])])
    items, _, _ = await svc.list_page(col.id, offset=0, page_size=10, search_text=None)
    data_id = items[0].id

    await svc.update(data_id, q="新名", indexes=["新别名1", "新别名2"])

    data, indexes, _ = await svc.detail(data_id)
    assert data.q == "新名"
    texts = {i.text for i in indexes}
    assert texts == {"新名", "新别名1", "新别名2"}
    tasks = await TaskRepository(db_session).claim(10)
    assert len(tasks) == 2  # push 1 + update 1


async def test_delete_data(db_session):
    col = await _make_virtual_collection(db_session)
    svc = DataService(db_session)
    await svc.push(col.id, [PushItem(q="x", a=None, indexes=[])])
    items, _, _ = await svc.list_page(col.id, offset=0, page_size=10, search_text=None)
    await svc.delete(items[0].id)
    with pytest.raises(NotFoundError):
        await svc.detail(items[0].id)
