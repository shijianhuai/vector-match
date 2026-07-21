import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vector_match.core.config import Settings
from vector_match.core.text import to_fts_tokens
from vector_match.db.models import TrainingTask
from vector_match.providers.embedding import EmbeddingClient, EmbeddingError, embed_in_batches
from vector_match.repositories.data import DataRepository
from vector_match.repositories.tasks import TaskRepository


async def process_batch(
    session_factory: async_sessionmaker[AsyncSession],
    embedding: EmbeddingClient,
    settings: Settings,
    tasks: list[TrainingTask],
) -> None:
    """对一批已 claim 的任务执行训练: 分词 + 批量 embedding + 回写向量。"""
    items: list[tuple[uuid.UUID, uuid.UUID, list[tuple[uuid.UUID, str]], str]] = []
    async with session_factory() as session:
        task_repo = TaskRepository(session)
        data_repo = DataRepository(session)
        for t in tasks:
            data = await data_repo.get(t.data_id)
            if data is None:
                await task_repo.mark_failed(t.id, "data deleted")
                continue
            indexes = await data_repo.list_valid_indexes(data.id, only_untrained=True)
            if not indexes:
                await task_repo.mark_done(t.id)
                continue
            items.append((t.id, data.id, [(i.id, i.text) for i in indexes], f"{data.q} {data.a or ''}"))
        await session.commit()

    if not items:
        return

    texts = [text for _, _, pairs, _ in items for _, text in pairs]
    try:
        vectors = await embed_in_batches(
            embedding,
            texts,
            batch_size=settings.embedding_batch_size,
            concurrency=settings.worker_concurrency,
        )
    except EmbeddingError as exc:
        async with session_factory() as session:
            task_repo = TaskRepository(session)
            for task_id, *_ in items:
                await task_repo.schedule_retry(task_id, str(exc), settings.worker_max_attempts)
            await session.commit()
        return

    pos = 0
    async with session_factory() as session:
        task_repo = TaskRepository(session)
        data_repo = DataRepository(session)
        for task_id, data_id, pairs, fts_source in items:
            for index_id, _ in pairs:
                await data_repo.set_index_vector(index_id, vectors[pos])
                pos += 1
            await data_repo.set_full_text_tokens(data_id, to_fts_tokens(fts_source))
            await task_repo.mark_done(task_id)
        await session.commit()
