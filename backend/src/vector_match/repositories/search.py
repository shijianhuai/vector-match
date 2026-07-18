import uuid
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.db.models import Collection, DatasetData


@dataclass
class HitRow:
    id: uuid.UUID
    q: str
    a: str | None
    dataset_id: uuid.UUID
    collection_id: uuid.UUID
    source_name: str


class SearchRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def vector_recall(
        self, dataset_id: uuid.UUID, query_vector: list[float], limit: int
    ) -> list[tuple[uuid.UUID, float]]:
        stmt = text(
            """
            SELECT di.data_id AS data_id, di.vector <=> :qv AS dist
            FROM data_indexes di
            JOIN dataset_data d ON d.id = di.data_id
            WHERE d.dataset_id = :ds AND d.isvalid = 1 AND di.isvalid = 1 AND di.vector IS NOT NULL
            ORDER BY dist
            LIMIT :lim
            """
        )
        result = await self.session.execute(stmt, {"ds": dataset_id, "qv": str(query_vector), "lim": limit})
        return [(row.data_id, float(row.dist)) for row in result]

    async def fts_recall(self, dataset_id: uuid.UUID, tokens: str, limit: int) -> list[tuple[uuid.UUID, float]]:
        stmt = text(
            """
            SELECT d.id AS data_id,
                   ts_rank(to_tsvector('simple', d.full_text_tokens), plainto_tsquery('simple', :q)) AS rank
            FROM dataset_data d
            WHERE d.dataset_id = :ds AND d.isvalid = 1
              AND to_tsvector('simple', d.full_text_tokens) @@ plainto_tsquery('simple', :q)
            ORDER BY rank DESC
            LIMIT :lim
            """
        )
        result = await self.session.execute(stmt, {"ds": dataset_id, "q": tokens, "lim": limit})
        return [(row.data_id, float(row.rank)) for row in result]

    async def hydrate(self, data_ids: list[uuid.UUID]) -> list[HitRow]:
        if not data_ids:
            return []
        stmt = (
            select(
                DatasetData.id,
                DatasetData.q,
                DatasetData.a,
                DatasetData.dataset_id,
                DatasetData.collection_id,
                Collection.name.label("source_name"),
            )
            .join(Collection, Collection.id == DatasetData.collection_id)
            .where(DatasetData.id.in_(data_ids), DatasetData.isvalid == 1)
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            HitRow(
                id=r.id,
                q=r.q,
                a=r.a,
                dataset_id=r.dataset_id,
                collection_id=r.collection_id,
                source_name=r.source_name,
            )
            for r in rows
        ]
