from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.api.deps import get_db, get_embedding, get_rerank, verify_api_key
from vector_match.api.schemas import SearchHitResponse, SearchRequest
from vector_match.core.config import Settings, get_settings
from vector_match.services.search import SearchParams, SearchService

router = APIRouter(prefix="/api/core/dataset", dependencies=[Depends(verify_api_key)])


@router.post("/search", response_model=list[SearchHitResponse])
async def search(
    req: SearchRequest,
    session: AsyncSession = Depends(get_db),
    embedding=Depends(get_embedding),
    rerank=Depends(get_rerank),
    settings: Settings = Depends(get_settings),
):
    params = SearchParams(
        dataset_id=req.dataset_id,
        text=req.text,
        top_k=req.top_k,
        similarity=req.similarity,
        search_mode=req.search_mode,
        using_re_rank=req.using_re_rank,
        rerank_model=req.rerank_model,
    )
    hits = await SearchService(session, embedding, rerank, settings).search(params)
    return [SearchHitResponse.model_validate(h) for h in hits]
