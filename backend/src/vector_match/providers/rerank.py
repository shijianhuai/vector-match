import asyncio

import httpx


class RerankError(Exception):
    pass


class RerankClient:
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

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int,
        model: str | None = None,
    ) -> list[float]:
        scores = [0.0] * len(documents)
        if not documents:
            return scores
        payload = {
            "model": model or self._model,
            "query": query,
            "documents": documents,
            "top_n": min(top_n, len(documents)),
        }
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                resp = await self._client.post("/rerank", json=payload)
                if resp.status_code == 200:
                    for item in resp.json().get("results", []):
                        scores[item["index"]] = float(item["relevance_score"])
                    return scores
                if resp.status_code == 429 or resp.status_code >= 500:
                    last_error = RerankError(f"rerank API {resp.status_code}: {resp.text[:200]}")
                else:
                    raise RerankError(f"rerank API {resp.status_code}: {resp.text[:200]}")
            except httpx.HTTPError as exc:
                last_error = RerankError(str(exc))
            await asyncio.sleep(min(2**attempt, 30))
        raise RerankError(f"rerank failed after {self._max_retries} attempts: {last_error}")
