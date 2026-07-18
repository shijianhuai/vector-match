import httpx
import pytest

from vector_match.providers.rerank import RerankClient, RerankError


def make_client(handler, max_retries=4):
    return RerankClient(
        base_url="http://test/v1",
        api_key="k",
        model="rerank-model",
        max_retries=max_retries,
        transport=httpx.MockTransport(handler),
    )


async def test_rerank_scores_aligned_with_documents():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {"index": 2, "relevance_score": 0.9},
                    {"index": 0, "relevance_score": 0.5},
                ]
            },
        )

    client = make_client(handler)
    scores = await client.rerank("基金", ["doc0", "doc1", "doc2"], top_n=3)
    assert scores == [0.5, 0.0, 0.9]
    await client.aclose()


async def test_rerank_uses_model_override():
    import json

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "other-model"
        return httpx.Response(200, json={"results": []})

    client = make_client(handler)
    await client.rerank("q", ["d"], top_n=1, model="other-model")
    await client.aclose()


async def test_rerank_retry_then_raise():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    client = make_client(handler, max_retries=2)
    with pytest.raises(RerankError):
        await client.rerank("q", ["d"], top_n=1)
    await client.aclose()
