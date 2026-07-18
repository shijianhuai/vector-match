from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from vector_match.core.config import Settings


def make_engine(settings: Settings):
    return create_async_engine(settings.database_url, pool_size=10, max_overflow=20)


def make_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
