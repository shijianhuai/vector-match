from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from vector_match.core.config import Settings, get_settings


async def verify_api_key(
    authorization: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing or malformed Authorization header")
    if authorization.removeprefix("Bearer ") not in settings.api_key_set:
        raise HTTPException(status_code=401, detail="invalid api key")


async def get_db(request: Request):
    factory = request.app.state.session_factory
    async with factory() as session:
        yield session


def get_embedding(request: Request):
    return request.app.state.embedding


def get_rerank(request: Request):
    return request.app.state.rerank
