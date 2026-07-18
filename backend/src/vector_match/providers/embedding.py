import asyncio

import httpx


class EmbeddingError(Exception):
    pass


class EmbeddingClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        max_retries: int = 4,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._model = model
        self._max_retries = max_retries
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                resp = await self._client.post("/embeddings", json={"model": self._model, "input": texts})
                if resp.status_code == 200:
                    data = sorted(resp.json()["data"], key=lambda d: d["index"])
                    return [d["embedding"] for d in data]
                if resp.status_code == 429 or resp.status_code >= 500:
                    last_error = EmbeddingError(f"embedding API {resp.status_code}: {resp.text[:200]}")
                else:
                    raise EmbeddingError(f"embedding API {resp.status_code}: {resp.text[:200]}")
            except httpx.HTTPError as exc:
                last_error = EmbeddingError(str(exc))
            await asyncio.sleep(min(2**attempt, 30))
        raise EmbeddingError(f"embedding failed after {self._max_retries} attempts: {last_error}")


async def embed_in_batches(
    client: EmbeddingClient,
    texts: list[str],
    batch_size: int = 64,
    concurrency: int = 4,
) -> list[list[float]]:
    semaphore = asyncio.Semaphore(concurrency)
    results: dict[int, list[float]] = {}

    async def one(offset: int, chunk: list[str]) -> None:
        async with semaphore:
            vectors = await client.embed(chunk)
        for j, v in enumerate(vectors):
            results[offset + j] = v

    chunks = [(i, texts[i : i + batch_size]) for i in range(0, len(texts), batch_size)]
    async with asyncio.TaskGroup() as tg:
        for offset, chunk in chunks:
            tg.create_task(one(offset, chunk))
    return [results[i] for i in range(len(texts))]
