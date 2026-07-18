import httpx
import pytest

from vector_match.providers.embedding import EmbeddingClient, EmbeddingError, embed_in_batches


def make_client(handler, max_retries=4):
    return EmbeddingClient(
        base_url="http://test/v1",
        api_key="k",
        model="m",
        max_retries=max_retries,
        transport=httpx.MockTransport(handler),
    )


async def test_embed_returns_vectors_in_input_order():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.2, 0.3]},
                    {"index": 0, "embedding": [0.1, 0.0]},
                ]
            },
        )

    client = make_client(handler)
    vectors = await client.embed(["a", "b"])
    assert vectors == [[0.1, 0.0], [0.2, 0.3]]
    await client.aclose()


async def test_embed_retries_on_429_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0]}]})

    client = make_client(handler)
    assert await client.embed(["x"]) == [[1.0]]
    assert calls["n"] == 2
    await client.aclose()


async def test_embed_raises_after_max_retries():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    client = make_client(handler, max_retries=2)
    with pytest.raises(EmbeddingError):
        await client.embed(["x"])
    await client.aclose()


async def test_embed_400_not_retried():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(400, json={"error": "bad input"})

    client = make_client(handler)
    with pytest.raises(EmbeddingError):
        await client.embed(["x"])
    assert calls["n"] == 1
    await client.aclose()


async def test_embed_empty_list():
    client = make_client(lambda r: httpx.Response(200, json={"data": []}))
    assert await client.embed([]) == []
    await client.aclose()


async def test_embed_in_batches_preserves_order():
    def handler(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.content)
        return httpx.Response(
            200, json={"data": [{"index": i, "embedding": [float(len(t))]} for i, t in enumerate(body["input"])]}
        )

    client = make_client(handler)
    texts = ["a" * i for i in range(1, 8)]  # 长度 1..7
    vectors = await embed_in_batches(client, texts, batch_size=3, concurrency=2)
    assert vectors == [[float(i)] for i in range(1, 8)]
    await client.aclose()


async def test_embed_in_batches_raises_embedding_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    client = make_client(handler, max_retries=1)
    with pytest.raises(EmbeddingError):  # 不得被包装成 ExceptionGroup
        await embed_in_batches(client, ["a", "b"], batch_size=1)
    await client.aclose()
