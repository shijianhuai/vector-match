from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from vector_match.api.routers import api_keys, auth, collections, data, datasets, health, search, users
from vector_match.core.config import get_settings
from vector_match.core.exceptions import ConflictError, NotFoundError, ProviderConfigError, ValidationError
from vector_match.db.session import make_engine, make_session_factory
from vector_match.providers.embedding import EmbeddingClient
from vector_match.providers.rerank import RerankClient
from vector_match.services.users import UserService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    engine = make_engine(settings)
    app.state.settings = settings
    app.state.session_factory = make_session_factory(engine)
    app.state.embedding = EmbeddingClient(
        settings.embedding_base_url, settings.embedding_api_key, settings.embedding_model
    )
    app.state.rerank = (
        RerankClient(settings.rerank_base_url, settings.rerank_api_key, settings.rerank_model)
        if settings.rerank_base_url
        else None
    )
    async with app.state.session_factory() as session:
        await UserService(session).seed_admin(settings)
    yield
    await app.state.embedding.aclose()
    if app.state.rerank is not None:
        await app.state.rerank.aclose()
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="vector-match", lifespan=lifespan)

    @app.exception_handler(NotFoundError)
    async def _not_found(request: Request, exc: NotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def _validation(request: Request, exc: ValidationError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def _conflict(request: Request, exc: ConflictError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ProviderConfigError)
    async def _provider_config(request: Request, exc: ProviderConfigError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(api_keys.router)
    app.include_router(datasets.router)
    app.include_router(collections.router)
    app.include_router(data.router)
    app.include_router(search.router)
    app.include_router(users.router)
    return app


app = create_app()
