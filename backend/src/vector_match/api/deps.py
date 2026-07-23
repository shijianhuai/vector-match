import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.core.config import Settings, get_settings
from vector_match.db.models import Collection, DatasetData, User
from vector_match.repositories.api_keys import ApiKeyRepository
from vector_match.repositories.members import DatasetMemberRepository
from vector_match.repositories.users import UserRepository

ROLE_LEVEL = {"owner": 3, "editor": 2, "viewer": 1}


def _has_enough_role(member, min_role: str) -> bool:
    if member is None:
        return False
    return ROLE_LEVEL[member.role] >= ROLE_LEVEL[min_role]


async def _check_role(user: User, dataset_id: uuid.UUID | None, min_role: str, db: AsyncSession) -> None:
    if user.is_superuser:
        return
    if dataset_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="missing required id")
    member = await DatasetMemberRepository(db).get_valid(dataset_id, user.id)
    if not _has_enough_role(member, min_role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="permission denied")


async def _uuid_from_raw(raw: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(raw))
    except (ValueError, TypeError):
        return None


async def _body_json(request: Request) -> dict[str, Any] | None:
    if request.method in ("GET", "HEAD"):
        return None
    try:
        body = await request.json()
    except Exception:
        return None
    if isinstance(body, dict):
        return body
    return None


async def _extract_dataset_id(request: Request) -> uuid.UUID | None:
    raw = (
        request.path_params.get("dataset_id")
        or request.query_params.get("id")
        or request.query_params.get("datasetId")
    )
    if raw:
        return await _uuid_from_raw(raw)
    body = await _body_json(request)
    if body is None:
        return None
    raw = body.get("id") or body.get("datasetId")
    if raw:
        return await _uuid_from_raw(raw)
    return None


async def _extract_collection_ids(request: Request) -> list[uuid.UUID] | None:
    raw = request.query_params.get("id") or request.query_params.get("collectionId")
    if raw:
        uid = await _uuid_from_raw(raw)
        return [uid] if uid else None
    body = await _body_json(request)
    if body is None:
        return None
    if "collectionIds" in body and isinstance(body["collectionIds"], list):
        ids = [await _uuid_from_raw(x) for x in body["collectionIds"]]
        if any(uid is None for uid in ids):
            return None
        return [uid for uid in ids if uid is not None]
    raw = body.get("id") or body.get("collectionId")
    if raw:
        uid = await _uuid_from_raw(raw)
        return [uid] if uid else None
    return None


async def _extract_data_ids(request: Request) -> list[uuid.UUID] | None:
    raw = request.query_params.get("id") or request.query_params.get("dataId")
    if raw:
        uid = await _uuid_from_raw(raw)
        return [uid] if uid else None
    body = await _body_json(request)
    if body is None:
        return None
    raw = body.get("id") or body.get("dataId")
    if raw:
        uid = await _uuid_from_raw(raw)
        return [uid] if uid else None
    return None


async def _resolve_collection_dataset(db: AsyncSession, collection_ids: list[uuid.UUID]) -> uuid.UUID:
    from sqlalchemy import select

    if not collection_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="missing collection id")
    stmt = select(Collection).where(Collection.id.in_(collection_ids), Collection.isvalid == 1)
    rows = list((await db.execute(stmt)).scalars().all())
    if len(rows) != len(collection_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="collection not found")
    dataset_ids = {r.dataset_id for r in rows}
    if len(dataset_ids) > 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="collections must belong to the same dataset"
        )
    return dataset_ids.pop()


async def _resolve_data_dataset(db: AsyncSession, data_ids: list[uuid.UUID]) -> uuid.UUID:
    from sqlalchemy import select

    if not data_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="missing data id")
    stmt = select(DatasetData).where(DatasetData.id.in_(data_ids), DatasetData.isvalid == 1)
    rows = list((await db.execute(stmt)).scalars().all())
    if len(rows) != len(data_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="data not found")
    collection_ids = [r.collection_id for r in rows]
    return await _resolve_collection_dataset(db, collection_ids)


def require_dataset_access(min_role: str) -> Callable[..., Awaitable[None]]:
    async def _dep(
        request: Request,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        dataset_id = await _extract_dataset_id(request)
        await _check_role(user, dataset_id, min_role, db)

    return _dep


def require_collection_access(min_role: str) -> Callable[..., Awaitable[None]]:
    async def _dep(
        request: Request,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        collection_ids = await _extract_collection_ids(request)
        if collection_ids is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="missing collection id")
        dataset_id = await _resolve_collection_dataset(db, collection_ids)
        await _check_role(user, dataset_id, min_role, db)

    return _dep


def require_data_access(min_role: str) -> Callable[..., Awaitable[None]]:
    async def _dep(
        request: Request,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        data_ids = await _extract_data_ids(request)
        if data_ids is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="missing data id")
        dataset_id = await _resolve_data_dataset(db, data_ids)
        await _check_role(user, dataset_id, min_role, db)

    return _dep


async def get_db(request: Request):
    factory = request.app.state.session_factory
    async with factory() as session:
        yield session


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing or malformed Authorization header")
    token = authorization.removeprefix("Bearer ")
    if token.startswith("sk-"):
        key_repo = ApiKeyRepository(session)
        api_key = await key_repo.get_by_key(token)
        if api_key is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")
        user_repo = UserRepository(session)
        user = await user_repo.get_by_id(api_key.user_id)
        if user is None or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user inactive or not found")
        await key_repo.touch_last_used(api_key)
        # 鉴权依赖中独立提交, 确保 last_used_at 落盘 (读请求后续无 commit)
        await session.commit()
        return user
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token expired") from None
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token") from None
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")
    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token") from None
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id_int)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user inactive or not found")
    return user


async def require_api_key_permission(user: User = Depends(get_current_user)) -> None:
    if not user.is_superuser and not user.allow_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="API Key 功能未开放，请联系管理员"  # noqa: RUF001
        )


async def require_superuser(
    user: User = Depends(get_current_user),
) -> None:
    if not user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="superuser required")


def get_embedding(request: Request):
    return request.app.state.embedding


def get_rerank(request: Request):
    return request.app.state.rerank
