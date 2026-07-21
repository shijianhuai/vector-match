from vector_match.core.config import Settings


def test_defaults():
    s = Settings()
    assert s.recall_limit == 60
    assert s.rerank_candidates == 30
    assert s.worker_max_attempts == 5
    assert s.database_url.startswith("postgresql+psycopg://")
    assert s.jwt_expire_minutes == 10080


def test_env_override(monkeypatch):
    monkeypatch.setenv("EMBEDDING_MODEL", "test-model")
    monkeypatch.setenv("RECALL_LIMIT", "42")
    s = Settings()
    assert s.embedding_model == "test-model"
    assert s.recall_limit == 42
