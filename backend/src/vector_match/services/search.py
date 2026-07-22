import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.core.config import Settings
from vector_match.core.exceptions import NotFoundError, ProviderConfigError, ValidationError
from vector_match.core.text import to_fts_tokens
from vector_match.providers.embedding import EmbeddingClient
from vector_match.providers.rerank import RerankClient
from vector_match.repositories.datasets import DatasetRepository
from vector_match.repositories.search import SearchRepository
from vector_match.services.fusion import rrf_fuse

SEARCH_MODES = ("embedding", "fullTextRecall", "mixedRecall")


@dataclass
class SearchParams:
    dataset_id: uuid.UUID
    text: str
    top_k: int = 10
    similarity: float = 0.0
    search_mode: str = "embedding"
    using_re_rank: bool = False
    rerank_model: str | None = None


@dataclass
class SearchHit:
    id: uuid.UUID
    q: str
    a: str | None
    dataset_id: uuid.UUID
    collection_id: uuid.UUID
    source_name: str
    score: float
    key_id: str | None


def _dedupe_keep_best(raw: list[tuple[uuid.UUID, float]], limit: int) -> list[tuple[uuid.UUID, float]]:
    """raw 按距离升序; 同一 data_id 只保留首次(最佳)命中, 得分 = 1 - 距离."""
    best: dict[uuid.UUID, float] = {}
    for data_id, dist in raw:
        best.setdefault(data_id, 1.0 - dist)
        if len(best) >= limit:
            break
    return sorted(best.items(), key=lambda kv: kv[1], reverse=True)


class SearchService:
    def __init__(
        self,
        session: AsyncSession,
        embedding: EmbeddingClient,
        rerank: RerankClient | None,
        settings: Settings,
    ):
        self.session = session
        self.embedding = embedding
        self.rerank = rerank
        self.settings = settings

    async def search(self, params: SearchParams) -> list[SearchHit]:
        if params.search_mode not in SEARCH_MODES:
            raise ValidationError(f"searchMode 必须是 {SEARCH_MODES} 之一")
        text = params.text.strip()
        if not text:
            raise ValidationError("text 不能为空")
        if await DatasetRepository(self.session).get(params.dataset_id) is None:
            raise NotFoundError("dataset not found")
        if params.using_re_rank and self.rerank is None:
            raise ProviderConfigError("rerank 未配置(RERANK_BASE_URL 为空)")

        repo = SearchRepository(self.session)
        limit = max(params.top_k, self.settings.recall_limit)
        vec_scored: list[tuple[uuid.UUID, float]] = []
        fts_scored: list[tuple[uuid.UUID, float]] = []

        if params.search_mode in ("embedding", "mixedRecall"):
            (qv,) = await self.embedding.embed([text])
            raw = await repo.vector_recall(params.dataset_id, qv, limit * 3)
            vec_scored = _dedupe_keep_best(raw, limit)

        if params.search_mode in ("fullTextRecall", "mixedRecall"):
            tokens = to_fts_tokens(text)
            if tokens:
                raw = await repo.fts_recall(params.dataset_id, tokens, limit)
                max_rank = raw[0][1] if raw else 0.0
                fts_scored = [(i, r / max_rank if max_rank > 0 else 0.0) for i, r in raw]

        if params.search_mode == "embedding":
            scored = vec_scored
        elif params.search_mode == "fullTextRecall":
            scored = fts_scored
        else:
            lists = [ids for ids in ([i for i, _ in vec_scored], [i for i, _ in fts_scored]) if ids]
            scored = rrf_fuse(lists)

        if params.using_re_rank:
            scored = await self._rerank(text, scored, repo, params.rerank_model)

        filterable = params.using_re_rank or params.search_mode == "embedding"
        if filterable and params.similarity > 0:
            scored = [(i, s) for i, s in scored if s >= params.similarity]
        scored = scored[: params.top_k]

        rows = {r.id: r for r in await repo.hydrate([i for i, _ in scored])}
        return [
            SearchHit(
                id=r.id,
                q=r.q,
                a=r.a,
                dataset_id=r.dataset_id,
                collection_id=r.collection_id,
                source_name=r.source_name,
                score=s,
                key_id=r.key_id,
            )
            for i, s in scored
            if (r := rows.get(i)) is not None
        ]

    async def _rerank(self, text, scored, repo, model) -> list[tuple[uuid.UUID, float]]:
        candidates = scored[: self.settings.rerank_candidates]
        rows = {r.id: r for r in await repo.hydrate([i for i, _ in candidates])}
        ids = [i for i, _ in candidates if i in rows]
        docs = [rows[i].q for i in ids]
        scores = await self.rerank.rerank(text, docs, top_n=len(docs), model=model)
        return sorted(zip(ids, scores, strict=True), key=lambda kv: kv[1], reverse=True)
