import asyncio
import logging
import signal

from vector_match.core.config import Settings
from vector_match.db.session import make_engine, make_session_factory
from vector_match.providers.embedding import EmbeddingClient
from vector_match.repositories.tasks import TaskRepository
from vector_match.worker.trainer import process_batch

logger = logging.getLogger(__name__)


async def run(settings: Settings) -> None:
    engine = make_engine(settings)
    session_factory = make_session_factory(engine)
    embedding = EmbeddingClient(settings.embedding_base_url, settings.embedding_api_key, settings.embedding_model)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    try:
        async with session_factory() as session:
            await TaskRepository(session).reset_stale_processing()
            await session.commit()

        while not stop.is_set():
            try:
                async with session_factory() as session:
                    tasks = await TaskRepository(session).claim(settings.worker_batch_size)
                    await session.commit()
                if not tasks:
                    try:
                        await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_interval)
                    except TimeoutError:
                        pass
                    continue
                await process_batch(session_factory, embedding, settings, tasks)
            except Exception:
                logger.exception("worker loop iteration failed; retrying after poll interval")
                try:
                    await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_interval)
                except TimeoutError:
                    pass
    finally:
        await embedding.aclose()
        await engine.dispose()
