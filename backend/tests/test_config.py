from vector_match.core.config import Settings


def test_api_key_set_parses_csv():
    s = Settings(api_keys=" key1 , key2,,key3 ")
    assert s.api_key_set == {"key1", "key2", "key3"}


def test_defaults():
    s = Settings()
    assert s.recall_limit == 60
    assert s.rerank_candidates == 30
    assert s.worker_max_attempts == 5
    assert s.database_url.startswith("postgresql+psycopg://")


def test_env_override(monkeypatch):
    monkeypatch.setenv("EMBEDDING_MODEL", "test-model")
    monkeypatch.setenv("RECALL_LIMIT", "42")
    s = Settings()
    assert s.embedding_model == "test-model"
    assert s.recall_limit == 42
