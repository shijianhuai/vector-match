from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/vector_match"
    jwt_secret: str
    jwt_expire_minutes: int = 10080
    admin_username: str = ""
    admin_password: str = ""

    # 阿里云百炼 OpenAI 兼容模式 endpoint(华北2-北京)
    embedding_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    embedding_api_key: str = ""
    embedding_model: str = "qwen3.7-text-embedding"
    # 百炼同步 embedding 接口单次输入条数上限(v3/v4 为 10 条)
    embedding_batch_size: int = 10

    rerank_base_url: str = ""
    rerank_api_key: str = ""
    rerank_model: str = "BAAI/bge-reranker-v2-m3"

    worker_poll_interval: float = 2.0
    worker_batch_size: int = 32
    worker_concurrency: int = 4
    worker_max_attempts: int = 5

    recall_limit: int = 60
    rerank_candidates: int = 30
    max_custom_indexes: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
