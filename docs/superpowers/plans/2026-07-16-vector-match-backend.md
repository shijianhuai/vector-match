# vector-match 后端实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 vector-match 后端：参考 FastGPT 知识库引擎的通用短文本匹配服务，支持语义/全文/混合检索与重排，异步训练队列写链路。

**Architecture:** FastAPI app + 独立 worker 进程 + PostgreSQL(pgvector) 三组件；PG 队列表 + `FOR UPDATE SKIP LOCKED` 做异步训练；向量召回（HNSW cosine）与全文召回（jieba 分词 + tsvector）双路，RRF 融合，可选 rerank 重排；embedding/rerank 均走 OpenAI 兼容 HTTP API。

**Tech Stack:** Python 3.13 / uv / FastAPI / SQLAlchemy 2 async / psycopg3 / pgvector-python / httpx / pydantic-settings / jieba / Alembic / pytest / ruff / Docker Compose

**Spec:** `docs/superpowers/specs/2026-07-16-vector-match-design.md`

## Global Constraints

- 全部实现代码位于 `backend/`；仓库根目录只保留 `docker-compose.yml`、`.env.example`、`README.md`、`docs/`、`scripts/`
- Python 代码内部一律 snake_case；JSON 报文一律 camelCase，用 pydantic v2 `alias_generator=to_camel` + `populate_by_name=True` 转换
- 每张表都有 `create_time`、`update_time`、`isvalid`（smallint，1 有效 / 0 无效）
- 不建外键约束；关联字段是普通字段 + 普通 B-tree 索引
- 删除一律软删除（`isvalid = 0`），级联软删在 service 层实现；所有查询带 `isvalid = 1` 过滤
- embedding 模型为部署级配置，向量维度由 `EMBEDDING_DIM` 决定（默认 1024），建表迁移时固定
- API 不套 `{code, message, data}` 信封：标准 HTTP 状态码 + FastAPI 默认 `{detail}` 错误体
- 除 `/health` 外所有接口要求 `Authorization: Bearer <key>`，密钥来自 `API_KEYS` 环境变量（逗号分隔）
- SQLAlchemy 全异步（`postgresql+psycopg://`）；repository 只 flush 不 commit，事务边界在 service 层
- 测试分两类：纯单测不依赖外部服务；DB 集成测试读取 `TEST_DATABASE_URL`，未设置时 skip
- 模型 provider（embedding/rerank）在测试中一律用 fake/mock，不调真实 API

---

### Task 1: 项目骨架迁移到 backend/

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/src/vector_match/__init__.py`
- Create: `backend/tests/test_smoke.py`
- Delete: `main.py`、`pyproject.toml`（根目录）
- Move: `.python-version` → `backend/.python-version`

**Interfaces:**
- Produces: `backend/` uv 项目布局，后续所有任务在此内工作；包名 `vector_match`（src 布局，可 `import vector_match`）

- [ ] **Step 1: 移动脚手架**

```bash
mkdir -p backend/src/vector_match backend/tests
git mv pyproject.toml backend/pyproject.toml
git mv .python-version backend/.python-version
git rm main.py
```

- [ ] **Step 2: 写 backend/pyproject.toml**

```toml
[project]
name = "vector-match"
version = "0.1.0"
description = "通用化文本匹配服务：语义/全文/混合检索 + 重排"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sqlalchemy[asyncio]>=2.0",
    "psycopg[binary]>=3.2",
    "pgvector>=0.3.6",
    "httpx>=0.28",
    "pydantic>=2.9",
    "pydantic-settings>=2.5",
    "jieba>=0.42.1",
    "alembic>=1.14",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.25",
    "asgi-lifespan>=2.1",
    "ruff>=0.9",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/vector_match"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
target-version = "py313"
src = ["src"]
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "ASYNC", "RUF"]
ignore = ["B008", "E501"]  # B008: FastAPI Depends 惯用法；E501: 行宽交给人工控制
```

- [ ] **Step 3: 写占位包与冒烟测试**

`backend/src/vector_match/__init__.py`：空文件。

`backend/tests/test_smoke.py`：

```python
def test_package_importable():
    import vector_match  # noqa: F401
```

- [ ] **Step 4: 安装依赖并跑通测试与 lint**

```bash
cd backend && uv sync && uv run pytest -v && uv run ruff check
```

Expected: 1 个测试 PASS；ruff 无输出（无错误）。

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "chore: move scaffold into backend/ with full dependency set"
```

---

### Task 2: 配置模块（Settings）

**Files:**
- Create: `backend/src/vector_match/core/__init__.py`（空文件）
- Create: `backend/src/vector_match/core/config.py`
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Produces: `Settings`（pydantic-settings，字段见下）、`get_settings() -> Settings`（lru_cache）。后续所有任务从 `Settings` 读取数据库、provider、worker、检索参数。

- [ ] **Step 1: 写失败测试**

```python
from vector_match.core.config import Settings


def test_api_key_set_parses_csv():
    s = Settings(api_keys=" key1 , key2,,key3 ")
    assert s.api_key_set == {"key1", "key2", "key3"}


def test_defaults():
    s = Settings()
    assert s.embedding_dim == 1024
    assert s.recall_limit == 60
    assert s.rerank_candidates == 30
    assert s.default_top_k == 10
    assert s.worker_max_attempts == 5
    assert s.database_url.startswith("postgresql+psycopg://")


def test_env_override(monkeypatch):
    monkeypatch.setenv("EMBEDDING_MODEL", "test-model")
    monkeypatch.setenv("RECALL_LIMIT", "42")
    s = Settings()
    assert s.embedding_model == "test-model"
    assert s.recall_limit == 42
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_config.py -v`
Expected: FAIL，`ModuleNotFoundError: vector_match.core`

- [ ] **Step 3: 实现 core/config.py**

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/vector_match"
    api_keys: str = "dev-key"

    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_api_key: str = ""
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024

    rerank_base_url: str = ""
    rerank_api_key: str = ""
    rerank_model: str = "BAAI/bge-reranker-v2-m3"

    worker_poll_interval: float = 2.0
    worker_batch_size: int = 32
    worker_concurrency: int = 4
    worker_max_attempts: int = 5

    recall_limit: int = 60
    rerank_candidates: int = 30
    default_top_k: int = 10

    @property
    def api_key_set(self) -> set[str]:
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_config.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/vector_match/core backend/tests/test_config.py
git commit -m "feat: add Settings config module"
```

---

### Task 3: 数据库基础（Base/Mixin/会话工厂）

**Files:**
- Create: `backend/src/vector_match/db/__init__.py`（空文件）
- Create: `backend/src/vector_match/db/base.py`
- Create: `backend/src/vector_match/db/session.py`
- Test: `backend/tests/test_db_session.py`

**Interfaces:**
- Produces: `Base`（DeclarativeBase）、`TimestampValidMixin`（create_time/update_time/isvalid）、`utcnow()`、`make_engine(settings)`、`make_session_factory(engine) -> async_sessionmaker`。Task 4 的模型继承 `Base` + `TimestampValidMixin`。

- [ ] **Step 1: 写失败测试**

```python
from vector_match.core.config import Settings
from vector_match.db.base import utcnow
from vector_match.db.session import make_engine, make_session_factory


def test_utcnow_tz_aware():
    assert utcnow().tzinfo is not None


def test_make_engine_and_session_factory():
    engine = make_engine(Settings())
    assert engine.dialect.name == "postgresql"
    factory = make_session_factory(engine)
    assert factory is not None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_db_session.py -v`
Expected: FAIL，`ModuleNotFoundError: vector_match.db`

- [ ] **Step 3: 实现**

`db/base.py`：

```python
from datetime import UTC, datetime

from sqlalchemy import DateTime, SmallInteger
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampValidMixin:
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    update_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    isvalid: Mapped[int] = mapped_column(SmallInteger, default=1)
```

`db/session.py`：

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from vector_match.core.config import Settings


def make_engine(settings: Settings):
    return create_async_engine(settings.database_url, pool_size=10, max_overflow=20)


def make_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_db_session.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/vector_match/db backend/tests/test_db_session.py
git commit -m "feat: add db base mixin and session factory"
```

---

### Task 4: ORM 模型（5 张表）

**Files:**
- Create: `backend/src/vector_match/db/models.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: `Base`、`TimestampValidMixin`（Task 3）
- Produces: `Dataset`、`Collection`、`DatasetData`、`DataIndex`、`TrainingTask`、`EMBEDDING_DIM`。字段名与 Task 5 迁移、Task 9-11 的 repository 一一对应，不得改名。

- [ ] **Step 1: 写失败测试**

```python
from vector_match.db.models import Collection, DataIndex, Dataset, DatasetData, TrainingTask


def test_tables_registered():
    assert Dataset.__tablename__ == "datasets"
    assert Collection.__tablename__ == "collections"
    assert DatasetData.__tablename__ == "dataset_data"
    assert DataIndex.__tablename__ == "data_indexes"
    assert TrainingTask.__tablename__ == "training_tasks"


def test_mixin_columns_present():
    for model in (Dataset, Collection, DatasetData, DataIndex, TrainingTask):
        cols = model.__table__.columns
        for name in ("create_time", "update_time", "isvalid"):
            assert name in cols, f"{model.__tablename__} missing {name}"


def test_vector_column_nullable_and_dim():
    col = DataIndex.__table__.columns["vector"]
    assert col.nullable is True
    assert col.type.dim == 1024


def test_data_columns():
    cols = DatasetData.__table__.columns
    assert cols["a"].nullable is True
    assert cols["full_text_tokens"].default.arg == ""
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_models.py -v`
Expected: FAIL，`ModuleNotFoundError: vector_match.db.models`

- [ ] **Step 3: 实现 db/models.py**

```python
import os
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from vector_match.db.base import Base, TimestampValidMixin, utcnow

EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "1024"))


class Dataset(TimestampValidMixin, Base):
    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    vector_model: Mapped[str] = mapped_column(Text)


class Collection(TimestampValidMixin, Base):
    __tablename__ = "collections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    name: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text)  # folder | virtual


class DatasetData(TimestampValidMixin, Base):
    __tablename__ = "dataset_data"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(index=True)
    collection_id: Mapped[uuid.UUID] = mapped_column(index=True)
    q: Mapped[str] = mapped_column(Text)
    a: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_text_tokens: Mapped[str] = mapped_column(Text, default="")


class DataIndex(TimestampValidMixin, Base):
    __tablename__ = "data_indexes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    data_id: Mapped[uuid.UUID] = mapped_column(index=True)
    type: Mapped[str] = mapped_column(Text, default="custom")  # default | custom
    text: Mapped[str] = mapped_column(Text)
    vector = mapped_column(Vector(EMBEDDING_DIM), nullable=True)


class TrainingTask(TimestampValidMixin, Base):
    __tablename__ = "training_tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    data_id: Mapped[uuid.UUID] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(Text, default="pending", index=True)
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    next_retry_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_models.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/vector_match/db/models.py backend/tests/test_models.py
git commit -m "feat: add ORM models for datasets/collections/data/indexes/tasks"
```

---

### Task 5: Alembic 初始化与初始迁移

**Files:**
- Create: `backend/alembic.ini`、`backend/alembic/env.py`、`backend/alembic/versions/0001_initial.py`
- Modify: `backend/pyproject.toml`（无需改动，alembic 已在依赖中）

**Interfaces:**
- Consumes: `Base`、`models`（Task 4）、`EMBEDDING_DIM` 环境变量
- Produces: `uv run alembic upgrade head` 可建出全部表与索引；测试 PG 容器供后续集成测试使用

- [ ] **Step 1: 生成 alembic 骨架**

```bash
cd backend && uv run alembic init alembic
```

- [ ] **Step 2: 替换 alembic/env.py 为以下内容**（sync 引擎跑迁移；URL 读环境变量）

```python
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from vector_match.db.base import Base
from vector_match.db import models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/vector_match",
)


def run_migrations_offline() -> None:
    context.configure(url=DATABASE_URL, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(DATABASE_URL, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

同时把 `alembic.ini` 中的 `sqlalchemy.url = ...` 行删除（URL 由 env.py 决定）。

- [ ] **Step 3: 手写初始迁移 alembic/versions/0001_initial.py**

```python
"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-16
"""

import os

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

DIM = int(os.environ.get("EMBEDDING_DIM", "1024"))


def _common_columns() -> list[sa.Column]:
    return [
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("isvalid", sa.SmallInteger(), nullable=False, server_default="1"),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "datasets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("vector_model", sa.Text(), nullable=False),
        *_common_columns(),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "collections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        *_common_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_collections_dataset_id", "collections", ["dataset_id"])
    op.create_index("ix_collections_parent_id", "collections", ["parent_id"])

    op.create_table(
        "dataset_data",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("collection_id", sa.Uuid(), nullable=False),
        sa.Column("q", sa.Text(), nullable=False),
        sa.Column("a", sa.Text(), nullable=True),
        sa.Column("full_text_tokens", sa.Text(), nullable=False, server_default=""),
        *_common_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dataset_data_dataset_id", "dataset_data", ["dataset_id"])
    op.create_index("ix_dataset_data_collection_id", "dataset_data", ["collection_id"])
    op.execute(
        "CREATE INDEX ix_dataset_data_fts ON dataset_data "
        "USING gin (to_tsvector('simple', full_text_tokens))"
    )

    op.create_table(
        "data_indexes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("data_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("vector", Vector(DIM), nullable=True),
        *_common_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_indexes_data_id", "data_indexes", ["data_id"])
    op.execute(
        "CREATE INDEX ix_data_indexes_vector_hnsw ON data_indexes "
        "USING hnsw (vector vector_cosine_ops)"
    )

    op.create_table(
        "training_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("data_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        *_common_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_training_tasks_data_id", "training_tasks", ["data_id"])
    op.create_index("ix_training_tasks_status", "training_tasks", ["status"])
    op.create_index("ix_training_tasks_next_retry_at", "training_tasks", ["next_retry_at"])


def downgrade() -> None:
    op.drop_table("training_tasks")
    op.drop_table("data_indexes")
    op.drop_table("dataset_data")
    op.drop_table("collections")
    op.drop_table("datasets")
```

- [ ] **Step 4: 启动测试 PG 并验证迁移**

```bash
docker run -d --name vm-test-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=vector_match_test -p 5432:5432 pgvector/pgvector:pg16
sleep 5
cd backend && DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/vector_match_test uv run alembic upgrade head
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/vector_match_test uv run alembic downgrade base
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/vector_match_test uv run alembic upgrade head
```

Expected: 三条命令均输出对应的 `Running upgrade / Running downgrade` 且无报错。该容器后续作为 `TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/vector_match_test` 的集成测试库保留运行。

- [ ] **Step 5: Commit**

```bash
git add backend/alembic backend/alembic.ini
git commit -m "feat: add alembic initial migration with hnsw and fts indexes"
```

---

### Task 6: 分词工具（jieba → FTS tokens）

**Files:**
- Create: `backend/src/vector_match/core/text.py`
- Test: `backend/tests/test_text.py`

**Interfaces:**
- Produces: `to_fts_tokens(text: str) -> str`。写入侧（worker）对 `q + " " + a` 调用，查询侧（SearchService）对查询文本调用，两侧必须用同一函数。

- [ ] **Step 1: 写失败测试**

```python
from vector_match.core.text import to_fts_tokens


def test_chinese_tokenized():
    tokens = to_fts_tokens("易方达蓝筹精选混合A")
    parts = tokens.split(" ")
    assert "易方达" in parts
    assert "蓝筹" in parts
    assert "A" in parts


def test_punctuation_filtered():
    tokens = to_fts_tokens("中证500指数(LOF)，A类!")
    for tok in tokens.split(" "):
        assert tok.strip() != ""
        assert all(ch not in tok for ch in "(),，!！")


def test_empty_input():
    assert to_fts_tokens("") == ""
    assert to_fts_tokens("，。！") == ""
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_text.py -v`
Expected: FAIL，`ModuleNotFoundError: vector_match.core.text`

- [ ] **Step 3: 实现 core/text.py**

```python
import re

import jieba

_KEEP = re.compile(r"[\w一-鿿]+", re.UNICODE)


def to_fts_tokens(text: str) -> str:
    """jieba cut_for_search 分词，过滤标点/空白 token，空格拼接。

    结果用于 PG `to_tsvector('simple', ...)` 全文检索，写入与查询两侧共用。
    """
    tokens = [t for t in jieba.cut_for_search(text) if _KEEP.fullmatch(t)]
    return " ".join(tokens)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_text.py -v`
Expected: 3 PASS（jieba 首次调用初始化词典，稍慢属正常）

- [ ] **Step 5: Commit**

```bash
git add backend/src/vector_match/core/text.py backend/tests/test_text.py
git commit -m "feat: add jieba-based fts tokenizer"
```

---

### Task 7: EmbeddingClient（OpenAI 兼容）

**Files:**
- Create: `backend/src/vector_match/providers/__init__.py`（空文件）
- Create: `backend/src/vector_match/providers/embedding.py`
- Test: `backend/tests/test_embedding_client.py`

**Interfaces:**
- Produces: `EmbeddingError`、`EmbeddingClient(base_url, api_key, model, timeout=60.0, max_retries=4, transport=None)`，方法 `embed(texts: list[str]) -> list[list[float]]`、`aclose()`；模块级 `embed_in_batches(client, texts, batch_size=64, concurrency=4) -> list[list[float]]`。`transport` 参数供测试注入 `httpx.MockTransport`。

- [ ] **Step 1: 写失败测试**

```python
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
        return httpx.Response(200, json={"data": [
            {"index": 1, "embedding": [0.2, 0.3]},
            {"index": 0, "embedding": [0.1, 0.0]},
        ]})

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
        return httpx.Response(200, json={
            "data": [{"index": i, "embedding": [float(len(t))]} for i, t in enumerate(body["input"])]
        })

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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_embedding_client.py -v`
Expected: FAIL，`ModuleNotFoundError: vector_match.providers`

- [ ] **Step 3: 实现 providers/embedding.py**

```python
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
                resp = await self._client.post(
                    "/embeddings", json={"model": self._model, "input": texts}
                )
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
    await asyncio.gather(*(one(offset, chunk) for offset, chunk in chunks))
    return [results[i] for i in range(len(texts))]
```

注意：并发必须用 `asyncio.gather`（异常按原样抛出），**不得用 `asyncio.TaskGroup`**——后者会把 `EmbeddingError` 包装成 `ExceptionGroup`，导致 worker 的 `except EmbeddingError` 失效。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_embedding_client.py -v`
Expected: 7 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/vector_match/providers backend/tests/test_embedding_client.py
git commit -m "feat: add OpenAI-compatible embedding client with retries"
```

---

### Task 8: RerankClient（OpenAI 兼容 /rerank）

**Files:**
- Create: `backend/src/vector_match/providers/rerank.py`
- Test: `backend/tests/test_rerank_client.py`

**Interfaces:**
- Produces: `RerankError`、`RerankClient(base_url, api_key, model, timeout=60.0, max_retries=4, transport=None)`，方法 `rerank(query, documents, top_n, model=None) -> list[float]`（返回与 documents 同序对齐的得分，未命中为 0.0）、`aclose()`。

- [ ] **Step 1: 写失败测试**

```python
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
        return httpx.Response(200, json={"results": [
            {"index": 2, "relevance_score": 0.9},
            {"index": 0, "relevance_score": 0.5},
        ]})

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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_rerank_client.py -v`
Expected: FAIL，`ModuleNotFoundError: vector_match.providers.rerank`

- [ ] **Step 3: 实现 providers/rerank.py**

```python
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_rerank_client.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/vector_match/providers/rerank.py backend/tests/test_rerank_client.py
git commit -m "feat: add rerank client"
```

---

### Task 9: 集成测试基座 + Dataset/Collection Repository

**Files:**
- Create: `backend/tests/conftest.py`
- Create: `backend/src/vector_match/repositories/__init__.py`（空文件）
- Create: `backend/src/vector_match/repositories/datasets.py`
- Create: `backend/src/vector_match/repositories/collections.py`
- Test: `backend/tests/test_dataset_repository.py`、`backend/tests/test_collection_repository.py`

**Interfaces:**
- Produces: `requires_db` 标记、`db_session` fixture（后续所有 DB 测试用）；`DatasetRepository(session)`：`create/get/list/update/soft_delete`；`CollectionRepository(session)`：`create/get/list_page/update/list_by_dataset/soft_delete_many`。所有 repo 方法只 flush 不 commit。

- [ ] **Step 1: 写 tests/conftest.py**

```python
import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
requires_db = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL 未设置，跳过集成测试")


@pytest.fixture(scope="session", autouse=True)
def _migrate_test_db():
    if not TEST_DATABASE_URL:
        return
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config("alembic.ini"), "head")


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()
    await engine.dispose()
```

- [ ] **Step 2: 写失败测试**

`tests/test_dataset_repository.py`：

```python
import pytest

from tests.conftest import requires_db
from vector_match.repositories.datasets import DatasetRepository

pytestmark = requires_db


async def test_create_get_list(db_session):
    repo = DatasetRepository(db_session)
    ds = await repo.create(name="基金库", description="fund", vector_model="m")
    assert ds.id is not None
    got = await repo.get(ds.id)
    assert got.name == "基金库"
    assert ds in await repo.list()


async def test_update_and_soft_delete(db_session):
    repo = DatasetRepository(db_session)
    ds = await repo.create(name="a", description="", vector_model="m")
    await repo.update(ds.id, name="b")
    assert (await repo.get(ds.id)).name == "b"
    await repo.soft_delete(ds.id)
    assert await repo.get(ds.id) is None
```

`tests/test_collection_repository.py`：

```python
from tests.conftest import requires_db
from vector_match.repositories.collections import CollectionRepository
from vector_match.repositories.datasets import DatasetRepository

pytestmark = requires_db


async def _make_dataset(db_session):
    return await DatasetRepository(db_session).create(name="d", description="", vector_model="m")


async def test_create_and_list_page(db_session):
    ds = await _make_dataset(db_session)
    repo = CollectionRepository(db_session)
    folder = await repo.create(dataset_id=ds.id, parent_id=None, name="目录", type="folder")
    c1 = await repo.create(dataset_id=ds.id, parent_id=folder.id, name="手动集A", type="virtual")
    await repo.create(dataset_id=ds.id, parent_id=folder.id, name="手动集B", type="virtual")

    items, total = await repo.list_page(ds.id, parent_id=folder.id, offset=0, page_size=10, search_text=None)
    assert total == 2 and len(items) == 2

    items, total = await repo.list_page(ds.id, parent_id=folder.id, offset=0, page_size=10, search_text="集A")
    assert total == 1 and items[0].id == c1.id


async def test_update_and_soft_delete_many(db_session):
    ds = await _make_dataset(db_session)
    repo = CollectionRepository(db_session)
    c1 = await repo.create(dataset_id=ds.id, parent_id=None, name="x", type="virtual")
    c2 = await repo.create(dataset_id=ds.id, parent_id=None, name="y", type="virtual")
    await repo.update(c1.id, name="x2")
    assert (await repo.get(c1.id)).name == "x2"
    await repo.soft_delete_many([c1.id, c2.id])
    assert await repo.get(c1.id) is None
    assert await repo.list_by_dataset(ds.id) == []
```

- [ ] **Step 3: 跑测试确认失败**

Run: `cd backend && TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/vector_match_test uv run pytest tests/test_dataset_repository.py tests/test_collection_repository.py -v`
Expected: FAIL，`ModuleNotFoundError: vector_match.repositories`（测试 PG 容器已在 Task 5 启动；未启动则先执行 Task 5 Step 4 的 docker run 命令）

- [ ] **Step 4: 实现**

`repositories/datasets.py`：

```python
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.db.models import Dataset


class DatasetRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, name: str, description: str, vector_model: str) -> Dataset:
        ds = Dataset(name=name, description=description, vector_model=vector_model)
        self.session.add(ds)
        await self.session.flush()
        return ds

    async def get(self, dataset_id: uuid.UUID) -> Dataset | None:
        stmt = select(Dataset).where(Dataset.id == dataset_id, Dataset.isvalid == 1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list(self) -> list[Dataset]:
        stmt = select(Dataset).where(Dataset.isvalid == 1).order_by(Dataset.create_time.desc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def update(self, dataset_id: uuid.UUID, name: str | None = None, description: str | None = None) -> Dataset | None:
        ds = await self.get(dataset_id)
        if ds is None:
            return None
        if name is not None:
            ds.name = name
        if description is not None:
            ds.description = description
        await self.session.flush()
        return ds

    async def soft_delete(self, dataset_id: uuid.UUID) -> None:
        stmt = update(Dataset).where(Dataset.id == dataset_id).values(isvalid=0)
        await self.session.execute(stmt)
```

`repositories/collections.py`：

```python
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.db.models import Collection


class CollectionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, dataset_id: uuid.UUID, parent_id: uuid.UUID | None, name: str, type: str) -> Collection:
        col = Collection(dataset_id=dataset_id, parent_id=parent_id, name=name, type=type)
        self.session.add(col)
        await self.session.flush()
        return col

    async def get(self, collection_id: uuid.UUID) -> Collection | None:
        stmt = select(Collection).where(Collection.id == collection_id, Collection.isvalid == 1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_page(
        self,
        dataset_id: uuid.UUID,
        parent_id: uuid.UUID | None,
        offset: int,
        page_size: int,
        search_text: str | None,
    ) -> tuple[list[Collection], int]:
        conditions = [Collection.dataset_id == dataset_id, Collection.isvalid == 1]
        if parent_id is None:
            conditions.append(Collection.parent_id.is_(None))
        else:
            conditions.append(Collection.parent_id == parent_id)
        if search_text:
            conditions.append(Collection.name.ilike(f"%{search_text}%"))
        total = await self.session.scalar(select(func.count()).select_from(Collection).where(*conditions))
        stmt = (
            select(Collection)
            .where(*conditions)
            .order_by(Collection.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list((await self.session.execute(stmt)).scalars().all()), int(total or 0)

    async def update(self, collection_id: uuid.UUID, name: str | None = None) -> Collection | None:
        col = await self.get(collection_id)
        if col is None:
            return None
        if name is not None:
            col.name = name
        await self.session.flush()
        return col

    async def list_by_dataset(self, dataset_id: uuid.UUID) -> list[Collection]:
        stmt = select(Collection).where(Collection.dataset_id == dataset_id, Collection.isvalid == 1)
        return list((await self.session.execute(stmt)).scalars().all())

    async def soft_delete_many(self, collection_ids: list[uuid.UUID]) -> None:
        if not collection_ids:
            return
        stmt = update(Collection).where(Collection.id.in_(collection_ids)).values(isvalid=0)
        await self.session.execute(stmt)
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/vector_match_test uv run pytest tests/test_dataset_repository.py tests/test_collection_repository.py -v`
Expected: 4 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/tests/conftest.py backend/tests/test_dataset_repository.py backend/tests/test_collection_repository.py backend/src/vector_match/repositories
git commit -m "feat: add dataset/collection repositories and db test fixtures"
```

---

### Task 10: DataRepository（数据 + 索引）

**Files:**
- Create: `backend/src/vector_match/repositories/data.py`
- Test: `backend/tests/test_data_repository.py`

**Interfaces:**
- Consumes: `DatasetRepository`、`CollectionRepository`（Task 9）
- Produces: `DataRepository(session)`：`create_many(rows)`、`get(data_id)`、`list_page(collection_id, offset, page_size, search_text)`、`list_by_ids(ids)`、`list_by_collections(collection_ids)`、`update_fields(data_id, q, a)`、`set_full_text_tokens(data_id, tokens)`、`soft_delete_many(data_ids)`、`add_index(data_id, text, type="custom")`、`list_valid_indexes(data_id, only_untrained=False)`、`invalidate_indexes(data_id)`、`invalidate_indexes_for_data(data_ids)`、`set_index_vector(index_id, vector)`、`list_trained_data_ids(data_ids) -> set[uuid.UUID]`

- [ ] **Step 1: 写失败测试**

```python
from tests.conftest import requires_db
from vector_match.repositories.collections import CollectionRepository
from vector_match.repositories.data import DataRepository
from vector_match.repositories.datasets import DatasetRepository

pytestmark = requires_db


async def _make_collection(db_session):
    ds = await DatasetRepository(db_session).create(name="d", description="", vector_model="m")
    return await CollectionRepository(db_session).create(dataset_id=ds.id, parent_id=None, name="c", type="virtual")


async def test_create_many_and_get(db_session):
    col = await _make_collection(db_session)
    repo = DataRepository(db_session)
    rows = await repo.create_many([
        {"dataset_id": col.dataset_id, "collection_id": col.id, "q": "易方达蓝筹精选混合", "a": "005827"},
        {"dataset_id": col.dataset_id, "collection_id": col.id, "q": "中欧医疗健康混合", "a": "003095"},
    ])
    assert len(rows) == 2
    got = await repo.get(rows[0].id)
    assert got.q == "易方达蓝筹精选混合" and got.full_text_tokens == ""


async def test_index_lifecycle(db_session):
    col = await _make_collection(db_session)
    repo = DataRepository(db_session)
    (row,) = await repo.create_many([{"dataset_id": col.dataset_id, "collection_id": col.id, "q": "q1", "a": None}])
    await repo.add_index(row.id, "q1", type="default")
    await repo.add_index(row.id, "别名1")

    untrained = await repo.list_valid_indexes(row.id, only_untrained=True)
    assert len(untrained) == 2

    await repo.set_index_vector(untrained[0].id, [0.0] * 1024)
    assert len(await repo.list_valid_indexes(row.id, only_untrained=True)) == 1
    assert await repo.list_trained_data_ids([row.id]) == {row.id}

    await repo.invalidate_indexes(row.id)
    assert await repo.list_valid_indexes(row.id) == []
    assert await repo.list_trained_data_ids([row.id]) == set()


async def test_list_page_search_and_soft_delete(db_session):
    col = await _make_collection(db_session)
    repo = DataRepository(db_session)
    rows = await repo.create_many([
        {"dataset_id": col.dataset_id, "collection_id": col.id, "q": "基金甲", "a": "001"},
        {"dataset_id": col.dataset_id, "collection_id": col.id, "q": "基金乙", "a": "002"},
    ])
    items, total = await repo.list_page(col.id, offset=0, page_size=10, search_text="基金甲")
    assert total == 1 and items[0].q == "基金甲"
    await repo.soft_delete_many([rows[0].id])
    assert await repo.get(rows[0].id) is None
    _, total = await repo.list_page(col.id, offset=0, page_size=10, search_text=None)
    assert total == 1


async def test_update_fields_and_tokens(db_session):
    col = await _make_collection(db_session)
    repo = DataRepository(db_session)
    (row,) = await repo.create_many([{"dataset_id": col.dataset_id, "collection_id": col.id, "q": "旧", "a": None}])
    await repo.update_fields(row.id, q="新", a="代码")
    await repo.set_full_text_tokens(row.id, "新 代码")
    got = await repo.get(row.id)
    assert got.q == "新" and got.a == "代码" and got.full_text_tokens == "新 代码"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && TEST_DATABASE_URL=... uv run pytest tests/test_data_repository.py -v`（TEST_DATABASE_URL 值同 Task 9）
Expected: FAIL，`ModuleNotFoundError: vector_match.repositories.data`

- [ ] **Step 3: 实现 repositories/data.py**

```python
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.db.models import DataIndex, DatasetData


class DataRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_many(self, rows: list[dict]) -> list[DatasetData]:
        objs = [DatasetData(**row) for row in rows]
        self.session.add_all(objs)
        await self.session.flush()
        return objs

    async def get(self, data_id: uuid.UUID) -> DatasetData | None:
        stmt = select(DatasetData).where(DatasetData.id == data_id, DatasetData.isvalid == 1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_page(
        self, collection_id: uuid.UUID, offset: int, page_size: int, search_text: str | None
    ) -> tuple[list[DatasetData], int]:
        conditions = [DatasetData.collection_id == collection_id, DatasetData.isvalid == 1]
        if search_text:
            conditions.append(DatasetData.q.ilike(f"%{search_text}%"))
        total = await self.session.scalar(select(func.count()).select_from(DatasetData).where(*conditions))
        stmt = (
            select(DatasetData)
            .where(*conditions)
            .order_by(DatasetData.create_time.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list((await self.session.execute(stmt)).scalars().all()), int(total or 0)

    async def list_by_ids(self, data_ids: list[uuid.UUID]) -> list[DatasetData]:
        if not data_ids:
            return []
        stmt = select(DatasetData).where(DatasetData.id.in_(data_ids), DatasetData.isvalid == 1)
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_by_collections(self, collection_ids: list[uuid.UUID]) -> list[DatasetData]:
        if not collection_ids:
            return []
        stmt = select(DatasetData).where(
            DatasetData.collection_id.in_(collection_ids), DatasetData.isvalid == 1
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def update_fields(self, data_id: uuid.UUID, q: str | None = None, a: str | None = None) -> None:
        obj = await self.get(data_id)
        if obj is None:
            return
        if q is not None:
            obj.q = q
        if a is not None:
            obj.a = a
        await self.session.flush()

    async def set_full_text_tokens(self, data_id: uuid.UUID, tokens: str) -> None:
        stmt = update(DatasetData).where(DatasetData.id == data_id).values(full_text_tokens=tokens)
        await self.session.execute(stmt)

    async def soft_delete_many(self, data_ids: list[uuid.UUID]) -> None:
        if not data_ids:
            return
        stmt = update(DatasetData).where(DatasetData.id.in_(data_ids)).values(isvalid=0)
        await self.session.execute(stmt)

    async def add_index(self, data_id: uuid.UUID, text: str, type: str = "custom") -> DataIndex:
        idx = DataIndex(data_id=data_id, text=text, type=type)
        self.session.add(idx)
        await self.session.flush()
        return idx

    async def list_valid_indexes(self, data_id: uuid.UUID, only_untrained: bool = False) -> list[DataIndex]:
        conditions = [DataIndex.data_id == data_id, DataIndex.isvalid == 1]
        if only_untrained:
            conditions.append(DataIndex.vector.is_(None))
        stmt = select(DataIndex).where(*conditions).order_by(DataIndex.create_time)
        return list((await self.session.execute(stmt)).scalars().all())

    async def invalidate_indexes(self, data_id: uuid.UUID) -> None:
        await self.invalidate_indexes_for_data([data_id])

    async def invalidate_indexes_for_data(self, data_ids: list[uuid.UUID]) -> None:
        if not data_ids:
            return
        stmt = update(DataIndex).where(DataIndex.data_id.in_(data_ids)).values(isvalid=0)
        await self.session.execute(stmt)

    async def set_index_vector(self, index_id: uuid.UUID, vector: list[float]) -> None:
        stmt = update(DataIndex).where(DataIndex.id == index_id).values(vector=vector)
        await self.session.execute(stmt)

    async def list_trained_data_ids(self, data_ids: list[uuid.UUID]) -> set[uuid.UUID]:
        if not data_ids:
            return set()
        stmt = (
            select(DataIndex.data_id)
            .where(
                DataIndex.data_id.in_(data_ids),
                DataIndex.isvalid == 1,
                DataIndex.type == "default",
                DataIndex.vector.is_not(None),
            )
            .distinct()
        )
        return set((await self.session.execute(stmt)).scalars().all())
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && TEST_DATABASE_URL=... uv run pytest tests/test_data_repository.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/vector_match/repositories/data.py backend/tests/test_data_repository.py
git commit -m "feat: add data/index repository"
```

---

### Task 11: TaskRepository（训练队列）

**Files:**
- Create: `backend/src/vector_match/repositories/tasks.py`
- Test: `backend/tests/test_task_repository.py`

**Interfaces:**
- Produces: `TaskRepository(session)`：`enqueue_many(data_ids)`、`claim(limit) -> list[TrainingTask]`（置 processing，调用方负责 commit）、`get(task_id)`、`mark_done(task_id)`、`mark_failed(task_id, reason)`、`schedule_retry(task_id, error, max_attempts)`、`fail_pending_for_data(data_ids, reason="data deleted")`、`reset_stale_processing(stale_minutes=10) -> int`

- [ ] **Step 1: 写失败测试**

```python
import uuid
from datetime import timedelta

from tests.conftest import requires_db
from vector_match.db.base import utcnow
from vector_match.repositories.tasks import TaskRepository

pytestmark = requires_db


async def test_enqueue_and_claim(db_session):
    repo = TaskRepository(db_session)
    data_ids = [uuid.uuid4(), uuid.uuid4()]
    await repo.enqueue_many(data_ids)
    tasks = await repo.claim(10)
    assert len(tasks) == 2
    assert all(t.status == "processing" for t in tasks)
    assert await repo.claim(10) == []


async def test_mark_done_and_failed(db_session):
    repo = TaskRepository(db_session)
    await repo.enqueue_many([uuid.uuid4()])
    (task,) = await repo.claim(1)
    await repo.mark_done(task.id)
    assert (await repo.get(task.id)).status == "done"
    await repo.mark_failed(task.id, "data deleted")
    got = await repo.get(task.id)
    assert got.status == "error" and got.last_error == "data deleted"


async def test_schedule_retry_backoff_then_error(db_session):
    repo = TaskRepository(db_session)
    await repo.enqueue_many([uuid.uuid4()])
    (task,) = await repo.claim(1)
    await repo.schedule_retry(task.id, "boom", max_attempts=3)
    got = await repo.get(task.id)
    assert got.status == "pending" and got.attempts == 1 and got.next_retry_at > utcnow()

    await repo.schedule_retry(task.id, "boom", max_attempts=1)
    got = await repo.get(task.id)
    assert got.status == "error" and got.attempts == 2


async def test_fail_pending_for_data(db_session):
    repo = TaskRepository(db_session)
    data_id = uuid.uuid4()
    await repo.enqueue_many([data_id, uuid.uuid4()])
    await repo.fail_pending_for_data([data_id])
    pending = await repo.claim(10)
    assert len(pending) == 1 and pending[0].data_id != data_id


async def test_reset_stale_processing(db_session):
    repo = TaskRepository(db_session)
    await repo.enqueue_many([uuid.uuid4()])
    (task,) = await repo.claim(1)
    task.update_time = utcnow() - timedelta(minutes=30)
    await db_session.flush()
    n = await repo.reset_stale_processing(stale_minutes=10)
    assert n == 1
    assert (await repo.get(task.id)).status == "pending"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && TEST_DATABASE_URL=... uv run pytest tests/test_task_repository.py -v`
Expected: FAIL，`ModuleNotFoundError: vector_match.repositories.tasks`

- [ ] **Step 3: 实现 repositories/tasks.py**

```python
import uuid
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.db.base import utcnow
from vector_match.db.models import TrainingTask


class TaskRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def enqueue_many(self, data_ids: list[uuid.UUID]) -> None:
        self.session.add_all([TrainingTask(data_id=d) for d in data_ids])
        await self.session.flush()

    async def claim(self, limit: int) -> list[TrainingTask]:
        stmt = (
            select(TrainingTask)
            .where(TrainingTask.status == "pending", TrainingTask.next_retry_at <= utcnow())
            .order_by(TrainingTask.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        tasks = list((await self.session.execute(stmt)).scalars().all())
        for t in tasks:
            t.status = "processing"
        await self.session.flush()
        return tasks

    async def get(self, task_id: uuid.UUID) -> TrainingTask | None:
        return await self.session.get(TrainingTask, task_id)

    async def mark_done(self, task_id: uuid.UUID) -> None:
        stmt = update(TrainingTask).where(TrainingTask.id == task_id).values(status="done")
        await self.session.execute(stmt)

    async def mark_failed(self, task_id: uuid.UUID, reason: str) -> None:
        stmt = update(TrainingTask).where(TrainingTask.id == task_id).values(status="error", last_error=reason[:500])
        await self.session.execute(stmt)

    async def schedule_retry(self, task_id: uuid.UUID, error: str, max_attempts: int) -> None:
        task = await self.get(task_id)
        if task is None:
            return
        task.attempts += 1
        task.last_error = error[:500]
        if task.attempts >= max_attempts:
            task.status = "error"
        else:
            task.status = "pending"
            task.next_retry_at = utcnow() + timedelta(minutes=min(2**task.attempts, 30))
        await self.session.flush()

    async def fail_pending_for_data(self, data_ids: list[uuid.UUID], reason: str = "data deleted") -> None:
        if not data_ids:
            return
        stmt = (
            update(TrainingTask)
            .where(TrainingTask.data_id.in_(data_ids), TrainingTask.status.in_(["pending", "processing"]))
            .values(status="error", last_error=reason)
        )
        await self.session.execute(stmt)

    async def reset_stale_processing(self, stale_minutes: int = 10) -> int:
        cutoff = utcnow() - timedelta(minutes=stale_minutes)
        stmt = (
            update(TrainingTask)
            .where(TrainingTask.status == "processing", TrainingTask.update_time < cutoff)
            .values(status="pending", next_retry_at=utcnow())
        )
        result = await self.session.execute(stmt)
        return result.rowcount
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && TEST_DATABASE_URL=... uv run pytest tests/test_task_repository.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/vector_match/repositories/tasks.py backend/tests/test_task_repository.py
git commit -m "feat: add training task queue repository"
```

---

### Task 12: 异常体系 + Dataset/Collection Service（级联软删）

**Files:**
- Create: `backend/src/vector_match/core/exceptions.py`
- Create: `backend/src/vector_match/services/__init__.py`（空文件）
- Create: `backend/src/vector_match/services/datasets.py`
- Create: `backend/src/vector_match/services/collections.py`
- Modify: `backend/src/vector_match/repositories/collections.py`（追加 `list_by_parents` 方法）
- Test: `backend/tests/test_dataset_collection_services.py`

**Interfaces:**
- Produces: `DomainError`、`NotFoundError`、`ValidationError`、`ProviderConfigError`（API 层映射 404/400）；`DatasetService(session)`：`create/list/detail/update/delete`；`CollectionService(session)`：`create/list_page/detail/update/delete`。service 方法内部 commit。

- [ ] **Step 1: 写失败测试**

```python
from uuid import uuid4

import pytest

from tests.conftest import requires_db
from vector_match.core.exceptions import NotFoundError, ValidationError
from vector_match.repositories.collections import CollectionRepository
from vector_match.repositories.data import DataRepository
from vector_match.repositories.datasets import DatasetRepository
from vector_match.services.collections import CollectionService
from vector_match.services.datasets import DatasetService

pytestmark = requires_db


async def test_dataset_crud(db_session):
    svc = DatasetService(db_session)
    ds = await svc.create(name="基金库", description="d")
    assert (await svc.detail(ds.id)).name == "基金库"
    await svc.update(ds.id, name="基金库2")
    assert (await svc.detail(ds.id)).name == "基金库2"
    await svc.delete(ds.id)
    with pytest.raises(NotFoundError):
        await svc.detail(ds.id)


async def test_dataset_delete_cascades(db_session):
    ds_svc = DatasetService(db_session)
    ds = await ds_svc.create(name="d", description="")
    col = await CollectionService(db_session).create(dataset_id=ds.id, parent_id=None, name="c", type="virtual")
    data_repo = DataRepository(db_session)
    (row,) = await data_repo.create_many([
        {"dataset_id": ds.id, "collection_id": col.id, "q": "基金A", "a": "001"}
    ])
    await data_repo.add_index(row.id, "基金A", type="default")

    await ds_svc.delete(ds.id)

    assert await DatasetRepository(db_session).get(ds.id) is None
    assert await CollectionRepository(db_session).get(col.id) is None
    assert await data_repo.get(row.id) is None
    assert await data_repo.list_valid_indexes(row.id) == []


async def test_collection_create_validations(db_session):
    svc = CollectionService(db_session)
    with pytest.raises(NotFoundError):
        await svc.create(dataset_id=uuid4(), parent_id=None, name="x", type="virtual")
    ds = await DatasetService(db_session).create(name="d", description="")
    with pytest.raises(ValidationError):
        await svc.create(dataset_id=ds.id, parent_id=None, name="x", type="bad-type")


async def test_collection_delete_cascades_to_children_and_data(db_session):
    ds = await DatasetService(db_session).create(name="d", description="")
    svc = CollectionService(db_session)
    folder = await svc.create(dataset_id=ds.id, parent_id=None, name="目录", type="folder")
    child = await svc.create(dataset_id=ds.id, parent_id=folder.id, name="子集", type="virtual")
    data_repo = DataRepository(db_session)
    (row,) = await data_repo.create_many([
        {"dataset_id": ds.id, "collection_id": child.id, "q": "基金B", "a": "002"}
    ])

    await svc.delete([folder.id])

    assert await CollectionRepository(db_session).get(child.id) is None
    assert await data_repo.get(row.id) is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && TEST_DATABASE_URL=... uv run pytest tests/test_dataset_collection_services.py -v`
Expected: FAIL，`ModuleNotFoundError: vector_match.services`

- [ ] **Step 3: 实现**

`core/exceptions.py`：

```python
class DomainError(Exception):
    """业务异常基类。"""


class NotFoundError(DomainError):
    pass


class ValidationError(DomainError):
    pass


class ProviderConfigError(DomainError):
    pass
```

`services/datasets.py`：

```python
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.core.exceptions import NotFoundError
from vector_match.db.models import Dataset
from vector_match.repositories.collections import CollectionRepository
from vector_match.repositories.data import DataRepository
from vector_match.repositories.datasets import DatasetRepository
from vector_match.repositories.tasks import TaskRepository


class DatasetService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.datasets = DatasetRepository(session)
        self.collections = CollectionRepository(session)
        self.data = DataRepository(session)
        self.tasks = TaskRepository(session)

    async def create(self, name: str, description: str = "", vector_model: str = "") -> Dataset:
        ds = await self.datasets.create(name=name, description=description, vector_model=vector_model)
        await self.session.commit()
        return ds

    async def list(self) -> list[Dataset]:
        return await self.datasets.list()

    async def detail(self, dataset_id: uuid.UUID) -> Dataset:
        ds = await self.datasets.get(dataset_id)
        if ds is None:
            raise NotFoundError("dataset not found")
        return ds

    async def update(self, dataset_id: uuid.UUID, name: str | None = None, description: str | None = None) -> Dataset:
        ds = await self.datasets.update(dataset_id, name=name, description=description)
        if ds is None:
            raise NotFoundError("dataset not found")
        await self.session.commit()
        return ds

    async def delete(self, dataset_id: uuid.UUID) -> None:
        ds = await self.datasets.get(dataset_id)
        if ds is None:
            raise NotFoundError("dataset not found")
        cols = await self.collections.list_by_dataset(dataset_id)
        col_ids = [c.id for c in cols]
        rows = await self.data.list_by_collections(col_ids)
        data_ids = [r.id for r in rows]
        await self.data.invalidate_indexes_for_data(data_ids)
        await self.data.soft_delete_many(data_ids)
        await self.tasks.fail_pending_for_data(data_ids)
        await self.collections.soft_delete_many(col_ids)
        await self.datasets.soft_delete(dataset_id)
        await self.session.commit()
```

`services/collections.py`：

```python
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.core.exceptions import NotFoundError, ValidationError
from vector_match.db.models import Collection
from vector_match.repositories.collections import CollectionRepository
from vector_match.repositories.data import DataRepository
from vector_match.repositories.datasets import DatasetRepository
from vector_match.repositories.tasks import TaskRepository

VALID_TYPES = ("folder", "virtual")


class CollectionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.collections = CollectionRepository(session)
        self.datasets = DatasetRepository(session)
        self.data = DataRepository(session)
        self.tasks = TaskRepository(session)

    async def create(self, dataset_id: uuid.UUID, parent_id: uuid.UUID | None, name: str, type: str) -> Collection:
        if type not in VALID_TYPES:
            raise ValidationError(f"type 必须是 {VALID_TYPES} 之一")
        if await self.datasets.get(dataset_id) is None:
            raise NotFoundError("dataset not found")
        if parent_id is not None and await self.collections.get(parent_id) is None:
            raise NotFoundError("parent collection not found")
        col = await self.collections.create(dataset_id=dataset_id, parent_id=parent_id, name=name, type=type)
        await self.session.commit()
        return col

    async def list_page(self, dataset_id, parent_id, offset, page_size, search_text):
        return await self.collections.list_page(dataset_id, parent_id, offset, page_size, search_text)

    async def detail(self, collection_id: uuid.UUID) -> Collection:
        col = await self.collections.get(collection_id)
        if col is None:
            raise NotFoundError("collection not found")
        return col

    async def update(self, collection_id: uuid.UUID, name: str | None = None) -> Collection:
        col = await self.collections.update(collection_id, name=name)
        if col is None:
            raise NotFoundError("collection not found")
        await self.session.commit()
        return col

    async def delete(self, collection_ids: list[uuid.UUID]) -> None:
        all_ids = await self._collect_with_children(collection_ids)
        rows = await self.data.list_by_collections(all_ids)
        data_ids = [r.id for r in rows]
        await self.data.invalidate_indexes_for_data(data_ids)
        await self.data.soft_delete_many(data_ids)
        await self.tasks.fail_pending_for_data(data_ids)
        await self.collections.soft_delete_many(all_ids)
        await self.session.commit()

    async def _collect_with_children(self, collection_ids: list[uuid.UUID]) -> list[uuid.UUID]:
        seen = set(collection_ids)
        frontier = list(collection_ids)
        while frontier:
            children = await self.collections.list_by_parents(frontier)
            frontier = [c.id for c in children if c.id not in seen]
            seen.update(frontier)
        return list(seen)
```

`repositories/collections.py` 追加方法（加在 `list_by_dataset` 之后）：

```python
    async def list_by_parents(self, parent_ids: list[uuid.UUID]) -> list[Collection]:
        if not parent_ids:
            return []
        stmt = select(Collection).where(Collection.parent_id.in_(parent_ids), Collection.isvalid == 1)
        return list((await self.session.execute(stmt)).scalars().all())
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && TEST_DATABASE_URL=... uv run pytest tests/test_dataset_collection_services.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/vector_match/core/exceptions.py backend/src/vector_match/services backend/src/vector_match/repositories/collections.py backend/tests/test_dataset_collection_services.py
git commit -m "feat: add dataset/collection services with cascade soft delete"
```

---

### Task 13: DataService（推送/更新/删除）

**Files:**
- Create: `backend/src/vector_match/services/data.py`
- Test: `backend/tests/test_data_service.py`（以及 Task 12 测试文件中涉及 DataService 的两个用例）

**Interfaces:**
- Consumes: 全部 repository（Task 9-11）、`NotFoundError`/`ValidationError`（Task 12）
- Produces: `PushItem`（dataclass：`q: str, a: str | None, indexes: list[str]`）；`DataService(session)`：`push(collection_id, items) -> int`、`update(data_id, q=None, a=None, indexes=None)`、`delete(data_id)`、`list_page(collection_id, offset, page_size, search_text) -> tuple[list, int, set[trained_ids]]`、`detail(data_id) -> tuple[DatasetData, list[DataIndex], bool]`

- [ ] **Step 1: 写失败测试**

```python
import pytest

from tests.conftest import requires_db
from vector_match.core.exceptions import NotFoundError, ValidationError
from vector_match.repositories.tasks import TaskRepository
from vector_match.services.collections import CollectionService
from vector_match.services.data import DataService, PushItem
from vector_match.services.datasets import DatasetService

pytestmark = requires_db


async def _make_virtual_collection(db_session, type="virtual"):
    ds = await DatasetService(db_session).create(name="d", description="")
    return await CollectionService(db_session).create(dataset_id=ds.id, parent_id=None, name="c", type=type)


async def test_push_creates_data_indexes_and_tasks(db_session):
    col = await _make_virtual_collection(db_session)
    svc = DataService(db_session)
    n = await svc.push(col.id, [
        PushItem(q="易方达蓝筹精选混合", a="005827", indexes=["易方达蓝筹", "蓝筹精选"]),
        PushItem(q="中欧医疗健康混合A", a="003095", indexes=[]),
    ])
    assert n == 2
    items, total, trained = await svc.list_page(col.id, offset=0, page_size=10, search_text=None)
    assert total == 2 and trained == set()
    data, indexes, is_trained = await svc.detail(items[0].id)
    assert is_trained is False
    assert {i.type for i in indexes} == {"default", "custom"}
    tasks = await TaskRepository(db_session).claim(10)
    assert len(tasks) == 2


async def test_push_validations(db_session):
    folder = await _make_virtual_collection(db_session, type="folder")
    svc = DataService(db_session)
    with pytest.raises(ValidationError):
        await svc.push(folder.id, [PushItem(q="x", a=None, indexes=[])])
    with pytest.raises(NotFoundError):
        from uuid import uuid4

        await svc.push(uuid4(), [PushItem(q="x", a=None, indexes=[])])
    col = await _make_virtual_collection(db_session)
    with pytest.raises(ValidationError):
        await svc.push(col.id, [PushItem(q="x", a=None, indexes=["a", "b", "c", "d", "e", "f"])])


async def test_update_rebuilds_indexes(db_session):
    col = await _make_virtual_collection(db_session)
    svc = DataService(db_session)
    await svc.push(col.id, [PushItem(q="旧名", a="001", indexes=["旧别名"])])
    items, _, _ = await svc.list_page(col.id, offset=0, page_size=10, search_text=None)
    data_id = items[0].id

    await svc.update(data_id, q="新名", indexes=["新别名1", "新别名2"])

    data, indexes, _ = await svc.detail(data_id)
    assert data.q == "新名"
    texts = sorted(i.text for i in indexes)
    assert texts == ["新名", "新别名1", "新别名2"]
    tasks = await TaskRepository(db_session).claim(10)
    assert len(tasks) == 2  # push 1 + update 1


async def test_delete_data(db_session):
    col = await _make_virtual_collection(db_session)
    svc = DataService(db_session)
    await svc.push(col.id, [PushItem(q="x", a=None, indexes=[])])
    items, _, _ = await svc.list_page(col.id, offset=0, page_size=10, search_text=None)
    await svc.delete(items[0].id)
    with pytest.raises(NotFoundError):
        await svc.detail(items[0].id)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && TEST_DATABASE_URL=... uv run pytest tests/test_data_service.py -v`
Expected: FAIL，`ModuleNotFoundError: vector_match.services.data`

- [ ] **Step 3: 实现 services/data.py**

```python
import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.core.exceptions import NotFoundError, ValidationError
from vector_match.db.models import DataIndex, DatasetData
from vector_match.repositories.collections import CollectionRepository
from vector_match.repositories.data import DataRepository
from vector_match.repositories.tasks import TaskRepository

MAX_BATCH = 200
MAX_CUSTOM_INDEXES = 5


@dataclass
class PushItem:
    q: str
    a: str | None = None
    indexes: list[str] = field(default_factory=list)


class DataService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.collections = CollectionRepository(session)
        self.data = DataRepository(session)
        self.tasks = TaskRepository(session)

    async def push(self, collection_id: uuid.UUID, items: list[PushItem]) -> int:
        col = await self.collections.get(collection_id)
        if col is None:
            raise NotFoundError("collection not found")
        if col.type != "virtual":
            raise ValidationError("只能向 virtual 类型集合推送数据")
        if not 1 <= len(items) <= MAX_BATCH:
            raise ValidationError(f"每批数据量须在 1~{MAX_BATCH} 之间")
        for item in items:
            if len(item.indexes) > MAX_CUSTOM_INDEXES:
                raise ValidationError(f"自定义索引最多 {MAX_CUSTOM_INDEXES} 个")

        rows = await self.data.create_many([
            {"dataset_id": col.dataset_id, "collection_id": col.id, "q": item.q, "a": item.a}
            for item in items
        ])
        for row, item in zip(rows, items, strict=True):
            await self.data.add_index(row.id, item.q, type="default")
            for text in item.indexes:
                await self.data.add_index(row.id, text, type="custom")
        await self.tasks.enqueue_many([r.id for r in rows])
        await self.session.commit()
        return len(rows)

    async def update(
        self,
        data_id: uuid.UUID,
        q: str | None = None,
        a: str | None = None,
        indexes: list[str] | None = None,
    ) -> None:
        obj = await self.data.get(data_id)
        if obj is None:
            raise NotFoundError("data not found")
        if indexes is not None and len(indexes) > MAX_CUSTOM_INDEXES:
            raise ValidationError(f"自定义索引最多 {MAX_CUSTOM_INDEXES} 个")
        new_q = q if q is not None else obj.q
        await self.data.update_fields(data_id, q=q, a=a)
        await self.data.invalidate_indexes(data_id)
        await self.data.add_index(data_id, new_q, type="default")
        for text in indexes or []:
            await self.data.add_index(data_id, text, type="custom")
        await self.tasks.enqueue_many([data_id])
        await self.session.commit()

    async def delete(self, data_id: uuid.UUID) -> None:
        obj = await self.data.get(data_id)
        if obj is None:
            raise NotFoundError("data not found")
        await self.data.invalidate_indexes(data_id)
        await self.data.soft_delete_many([data_id])
        await self.tasks.fail_pending_for_data([data_id])
        await self.session.commit()

    async def list_page(
        self, collection_id: uuid.UUID, offset: int, page_size: int, search_text: str | None
    ) -> tuple[list[DatasetData], int, set[uuid.UUID]]:
        items, total = await self.data.list_page(collection_id, offset, page_size, search_text)
        trained = await self.data.list_trained_data_ids([i.id for i in items])
        return items, total, trained

    async def detail(self, data_id: uuid.UUID) -> tuple[DatasetData, list[DataIndex], bool]:
        obj = await self.data.get(data_id)
        if obj is None:
            raise NotFoundError("data not found")
        indexes = await self.data.list_valid_indexes(data_id)
        trained = data_id in await self.data.list_trained_data_ids([data_id])
        return obj, indexes, trained
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && TEST_DATABASE_URL=... uv run pytest tests/test_data_service.py tests/test_dataset_collection_services.py -v`
Expected: 4 + 4 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/vector_match/services/data.py backend/tests/test_data_service.py backend/tests/test_dataset_collection_services.py
git commit -m "feat: add data service with push/update/delete"
```

---

### Task 14: SearchRepository（向量/全文召回 SQL）

**Files:**
- Create: `backend/src/vector_match/repositories/search.py`
- Test: `backend/tests/test_search_repository.py`

**Interfaces:**
- Consumes: `DataRepository`（Task 10，构造夹具数据）
- Produces: `HitRow`（dataclass：`id/q/a/dataset_id/collection_id/source_name`）；`SearchRepository(session)`：`vector_recall(dataset_id, query_vector, limit) -> list[tuple[uuid.UUID, float]]`（按距离升序）、`fts_recall(dataset_id, tokens, limit) -> list[tuple[uuid.UUID, float]]`（按 rank 降序）、`hydrate(data_ids) -> list[HitRow]`

- [ ] **Step 1: 写失败测试**

```python
from tests.conftest import requires_db
from vector_match.repositories.collections import CollectionRepository
from vector_match.repositories.data import DataRepository
from vector_match.repositories.datasets import DatasetRepository
from vector_match.repositories.search import SearchRepository

pytestmark = requires_db

DIM = 1024


def _unit_vec(i: int) -> list[float]:
    v = [0.0] * DIM
    v[i] = 1.0
    return v


async def _fixture(db_session):
    ds = await DatasetRepository(db_session).create(name="d", description="", vector_model="m")
    col = await CollectionRepository(db_session).create(dataset_id=ds.id, parent_id=None, name="基金集", type="virtual")
    repo = DataRepository(db_session)
    r1, r2 = await repo.create_many([
        {"dataset_id": ds.id, "collection_id": col.id, "q": "易方达蓝筹精选混合", "a": "005827"},
        {"dataset_id": ds.id, "collection_id": col.id, "q": "中欧医疗健康混合", "a": "003095"},
    ])
    i1 = await repo.add_index(r1.id, "易方达蓝筹精选混合", type="default")
    i2 = await repo.add_index(r2.id, "中欧医疗健康混合", type="default")
    await repo.set_index_vector(i1.id, _unit_vec(0))
    await repo.set_index_vector(i2.id, _unit_vec(1))
    await repo.set_full_text_tokens(r1.id, "易方达 蓝筹 精选 混合")
    await repo.set_full_text_tokens(r2.id, "中欧 医疗 健康 混合")
    return r1, r2


async def test_vector_recall_orders_by_distance(db_session):
    r1, r2 = await _fixture(db_session)
    repo = SearchRepository(db_session)
    hits = await repo.vector_recall(r1.dataset_id, _unit_vec(0), limit=10)
    assert hits[0][0] == r1.id
    assert hits[0][1] < 1e-6
    assert hits[1][0] == r2.id


async def test_vector_recall_skips_untrained_and_deleted(db_session):
    r1, r2 = await _fixture(db_session)
    repo = SearchRepository(db_session)
    data_repo = DataRepository(db_session)
    await data_repo.soft_delete_many([r2.id])
    hits = await repo.vector_recall(r1.dataset_id, _unit_vec(1), limit=10)
    assert [h[0] for h in hits] == [r1.id]


async def test_fts_recall(db_session):
    r1, r2 = await _fixture(db_session)
    repo = SearchRepository(db_session)
    hits = await repo.fts_recall(r1.dataset_id, "蓝筹", limit=10)
    assert [h[0] for h in hits] == [r1.id]
    hits = await repo.fts_recall(r1.dataset_id, "混合", limit=10)
    assert len(hits) == 2  # 两条都含「混合」


async def test_hydrate_returns_source_name(db_session):
    r1, r2 = await _fixture(db_session)
    repo = SearchRepository(db_session)
    rows = await repo.hydrate([r1.id, r2.id])
    by_id = {r.id: r for r in rows}
    assert by_id[r1.id].source_name == "基金集"
    assert by_id[r2.id].a == "003095"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && TEST_DATABASE_URL=... uv run pytest tests/test_search_repository.py -v`
Expected: FAIL，`ModuleNotFoundError: vector_match.repositories.search`

- [ ] **Step 3: 实现 repositories/search.py**

```python
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

    async def fts_recall(
        self, dataset_id: uuid.UUID, tokens: str, limit: int
    ) -> list[tuple[uuid.UUID, float]]:
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && TEST_DATABASE_URL=... uv run pytest tests/test_search_repository.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/vector_match/repositories/search.py backend/tests/test_search_repository.py
git commit -m "feat: add vector/fts recall repository"
```

---

### Task 15: RRF 融合 + SearchService 检索管线

**Files:**
- Create: `backend/src/vector_match/services/fusion.py`
- Create: `backend/src/vector_match/services/search.py`
- Test: `backend/tests/test_fusion.py`、`backend/tests/test_search_service.py`

**Interfaces:**
- Consumes: `SearchRepository`（Task 14）、`EmbeddingClient`/`RerankClient` 接口（Task 7/8，测试用同签名 fake）、`Settings`（Task 2）、`to_fts_tokens`（Task 6）
- Produces: `rrf_fuse(rank_lists, k=60) -> list[tuple[uuid.UUID, float]]`；`SearchParams`（dataclass）、`SearchHit`（dataclass）、`SearchService(session, embedding, rerank, settings).search(params) -> list[SearchHit]`

- [ ] **Step 1: 写失败测试**

`tests/test_fusion.py`：

```python
from uuid import uuid4

from vector_match.services.fusion import rrf_fuse


def test_rrf_orders_by_summed_score():
    a, b, c = uuid4(), uuid4(), uuid4()
    fused = rrf_fuse([[a, b], [b, c]])
    assert fused[0][0] == b  # 两路都命中，排第一
    assert fused[0][1] == 1 / 61 + 1 / 61
    assert {i for i, _ in fused} == {a, b, c}


def test_rrf_empty_lists():
    assert rrf_fuse([]) == []
    assert rrf_fuse([[]]) == []
```

`tests/test_search_service.py`：

```python
import pytest

from tests.conftest import requires_db
from vector_match.core.exceptions import NotFoundError, ProviderConfigError, ValidationError
from vector_match.core.config import Settings
from vector_match.repositories.collections import CollectionRepository
from vector_match.repositories.data import DataRepository
from vector_match.repositories.datasets import DatasetRepository
from vector_match.services.search import SearchParams, SearchService

pytestmark = requires_db

DIM = 1024


def _unit_vec(i: int) -> list[float]:
    v = [0.0] * DIM
    v[i] = 1.0
    return v


class FakeEmbedding:
    def __init__(self, vector):
        self._vector = vector

    async def embed(self, texts):
        return [self._vector for _ in texts]


class FakeRerank:
    def __init__(self, scores):
        self._scores = scores

    async def rerank(self, query, documents, top_n, model=None):
        return self._scores[: len(documents)]


async def _fixture(db_session):
    ds = await DatasetRepository(db_session).create(name="d", description="", vector_model="m")
    col = await CollectionRepository(db_session).create(dataset_id=ds.id, parent_id=None, name="基金集", type="virtual")
    repo = DataRepository(db_session)
    r1, r2 = await repo.create_many([
        {"dataset_id": ds.id, "collection_id": col.id, "q": "易方达蓝筹精选混合", "a": "005827"},
        {"dataset_id": ds.id, "collection_id": col.id, "q": "中欧医疗健康混合", "a": "003095"},
    ])
    i1 = await repo.add_index(r1.id, "易方达蓝筹精选混合", type="default")
    i2 = await repo.add_index(r2.id, "中欧医疗健康混合", type="default")
    await repo.set_index_vector(i1.id, _unit_vec(0))
    await repo.set_index_vector(i2.id, _unit_vec(1))
    await repo.set_full_text_tokens(r1.id, "易方达 蓝筹 精选 混合")
    await repo.set_full_text_tokens(r2.id, "中欧 医疗 健康 混合")
    return ds, r1, r2


def _params(ds, **kw):
    return SearchParams(dataset_id=ds.id, text="蓝筹", **kw)


async def test_embedding_mode(db_session):
    ds, r1, r2 = await _fixture(db_session)
    svc = SearchService(db_session, FakeEmbedding(_unit_vec(0)), None, Settings())
    hits = await svc.search(_params(ds, search_mode="embedding"))
    assert hits[0].id == r1.id
    assert hits[0].score == pytest.approx(1.0, abs=1e-6)
    assert hits[0].source_name == "基金集"


async def test_embedding_similarity_filter(db_session):
    ds, r1, r2 = await _fixture(db_session)
    svc = SearchService(db_session, FakeEmbedding(_unit_vec(0)), None, Settings())
    hits = await svc.search(_params(ds, search_mode="embedding", similarity=0.5))
    assert [h.id for h in hits] == [r1.id]  # r2 得分约 0 被过滤


async def test_fulltext_mode(db_session):
    ds, r1, r2 = await _fixture(db_session)
    svc = SearchService(db_session, FakeEmbedding(_unit_vec(0)), None, Settings())
    hits = await svc.search(_params(ds, text="蓝筹", search_mode="fullTextRecall"))
    assert hits[0].id == r1.id


async def test_mixed_mode_fuses(db_session):
    ds, r1, r2 = await _fixture(db_session)
    svc = SearchService(db_session, FakeEmbedding(_unit_vec(0)), None, Settings())
    hits = await svc.search(_params(ds, search_mode="mixedRecall"))
    assert hits[0].id == r1.id
    assert len(hits) == 2


async def test_rerank_reorders(db_session):
    ds, r1, r2 = await _fixture(db_session)
    svc = SearchService(db_session, FakeEmbedding(_unit_vec(0)), FakeRerank([0.1, 0.9]), Settings())
    hits = await svc.search(_params(ds, search_mode="embedding", using_re_rank=True))
    assert hits[0].id == r2.id and hits[0].score == pytest.approx(0.9)


async def test_validations(db_session):
    ds, _, _ = await _fixture(db_session)
    svc = SearchService(db_session, FakeEmbedding(_unit_vec(0)), None, Settings())
    with pytest.raises(ValidationError):
        await svc.search(_params(ds, text="  "))
    with pytest.raises(ValidationError):
        await svc.search(_params(ds, search_mode="bad"))
    with pytest.raises(ProviderConfigError):
        await svc.search(_params(ds, using_re_rank=True))
    with pytest.raises(NotFoundError):
        from uuid import uuid4

        await svc.search(_params(ds, dataset_id=uuid4()))
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && TEST_DATABASE_URL=... uv run pytest tests/test_fusion.py tests/test_search_service.py -v`
Expected: FAIL，`ModuleNotFoundError: vector_match.services.search`（fusion 同样不存在）

- [ ] **Step 3: 实现**

`services/fusion.py`：

```python
import uuid


def rrf_fuse(rank_lists: list[list[uuid.UUID]], k: int = 60) -> list[tuple[uuid.UUID, float]]:
    scores: dict[uuid.UUID, float] = {}
    for ids in rank_lists:
        for rank, doc_id in enumerate(ids, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
```

`services/search.py`：

```python
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


def _dedupe_keep_best(
    raw: list[tuple[uuid.UUID, float]], limit: int
) -> list[tuple[uuid.UUID, float]]:
    """raw 按距离升序；同一 data_id 只保留首次（最佳）命中，得分 = 1 - 距离。"""
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
            raise ProviderConfigError("rerank 未配置（RERANK_BASE_URL 为空）")

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
                id=r.id, q=r.q, a=r.a, dataset_id=r.dataset_id,
                collection_id=r.collection_id, source_name=r.source_name, score=s,
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && TEST_DATABASE_URL=... uv run pytest tests/test_fusion.py tests/test_search_service.py -v`
Expected: 2 + 6 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/vector_match/services/fusion.py backend/src/vector_match/services/search.py backend/tests/test_fusion.py backend/tests/test_search_service.py
git commit -m "feat: add search pipeline with rrf fusion and rerank"
```

---

### Task 16: API 骨架（app/鉴权/schemas/异常映射/datasets 路由）

**Files:**
- Create: `backend/src/vector_match/api/__init__.py`（空文件）、`backend/src/vector_match/api/routers/__init__.py`（空文件）
- Create: `backend/src/vector_match/api/deps.py`
- Create: `backend/src/vector_match/api/schemas.py`
- Create: `backend/src/vector_match/api/routers/health.py`
- Create: `backend/src/vector_match/api/routers/datasets.py`
- Create: `backend/src/vector_match/main.py`
- Modify: `backend/tests/conftest.py`（追加 `api_app` / `client` fixture）
- Test: `backend/tests/test_api_app.py`

**Interfaces:**
- Consumes: `DatasetService`（Task 12）、`Settings`（Task 2）
- Produces: `create_app()`、`verify_api_key`、`get_db`、`get_embedding`、`get_rerank` 依赖；`CamelModel` 基类与全部 schema；`/health` 与 datasets 五个端点。后续 Task 17/18 复用同一批 schema 与依赖。

- [ ] **Step 1: 写失败测试**（`client` fixture 在 Step 3 中加入 conftest，此处直接使用）

```python
from tests.conftest import requires_db

pytestmark = requires_db


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200 and resp.json() == {"status": "ok"}


async def test_auth_required(client):
    resp = await client.get("/api/core/dataset/list", headers={"Authorization": ""})
    assert resp.status_code == 401
    resp = await client.get("/api/core/dataset/list", headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401


async def test_dataset_crud_flow(client):
    resp = await client.post("/api/core/dataset/create", json={"name": "基金库", "description": "fund"})
    assert resp.status_code == 200
    dataset_id = resp.json()["id"]

    resp = await client.get("/api/core/dataset/list")
    assert any(d["id"] == dataset_id for d in resp.json())
    assert "vectorModel" in resp.json()[0]  # 对外驼峰

    resp = await client.get("/api/core/dataset/detail", params={"id": dataset_id})
    assert resp.json()["name"] == "基金库"

    resp = await client.put("/api/core/dataset/update", json={"id": dataset_id, "name": "基金库2"})
    assert resp.status_code == 200
    resp = await client.get("/api/core/dataset/detail", params={"id": dataset_id})
    assert resp.json()["name"] == "基金库2"

    resp = await client.delete("/api/core/dataset/delete", params={"id": dataset_id})
    assert resp.status_code == 200
    resp = await client.get("/api/core/dataset/detail", params={"id": dataset_id})
    assert resp.status_code == 404
    assert "detail" in resp.json()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && TEST_DATABASE_URL=... uv run pytest tests/test_api_app.py -v`
Expected: FAIL，`ModuleNotFoundError: vector_match.api`

- [ ] **Step 3: 实现**

`api/deps.py`：

```python
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from vector_match.core.config import Settings, get_settings


async def verify_api_key(
    authorization: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing or malformed Authorization header")
    if authorization.removeprefix("Bearer ") not in settings.api_key_set:
        raise HTTPException(status_code=401, detail="invalid api key")


async def get_db(request: Request):
    factory = request.app.state.session_factory
    async with factory() as session:
        yield session


def get_embedding(request: Request):
    return request.app.state.embedding


def get_rerank(request: Request):
    return request.app.state.rerank
```

`api/schemas.py`：

```python
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class DatasetCreateRequest(CamelModel):
    name: str = Field(min_length=1)
    description: str = ""


class DatasetUpdateRequest(CamelModel):
    id: uuid.UUID
    name: str | None = Field(default=None, min_length=1)
    description: str | None = None


class DatasetResponse(CamelModel):
    id: uuid.UUID
    name: str
    description: str
    vector_model: str


class IdResponse(CamelModel):
    id: uuid.UUID


class CollectionCreateRequest(CamelModel):
    dataset_id: uuid.UUID
    parent_id: uuid.UUID | None = None
    name: str = Field(min_length=1)
    type: Literal["folder", "virtual"]


class CollectionUpdateRequest(CamelModel):
    id: uuid.UUID
    name: str = Field(min_length=1)


class CollectionDeleteRequest(CamelModel):
    collection_ids: list[uuid.UUID] = Field(min_length=1)


class CollectionResponse(CamelModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    type: str


class CollectionListResponse(CamelModel):
    list: list[CollectionResponse]
    total: int


class IndexInput(CamelModel):
    text: str = Field(min_length=1)


class IndexResponse(CamelModel):
    type: str
    text: str


class PushDataItem(CamelModel):
    q: str = Field(min_length=1)
    a: str | None = None
    indexes: list[IndexInput] = Field(default_factory=list, max_length=5)


class PushDataRequest(CamelModel):
    collection_id: uuid.UUID
    data: list[PushDataItem] = Field(min_length=1, max_length=200)


class PushDataResponse(CamelModel):
    insert_len: int


class DataItemResponse(CamelModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    collection_id: uuid.UUID
    q: str
    a: str | None
    trained: bool


class DataListResponse(CamelModel):
    list: list[DataItemResponse]
    total: int


class DataDetailResponse(CamelModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    collection_id: uuid.UUID
    q: str
    a: str | None
    trained: bool
    indexes: list[IndexResponse]


class DataUpdateRequest(CamelModel):
    data_id: uuid.UUID
    q: str | None = Field(default=None, min_length=1)
    a: str | None = None
    indexes: list[IndexInput] | None = None


class SearchRequest(CamelModel):
    dataset_id: uuid.UUID
    text: str = Field(min_length=1)
    top_k: int = Field(default=10, ge=1, le=100)
    similarity: float = Field(default=0.0, ge=0.0, le=1.0)
    search_mode: Literal["embedding", "fullTextRecall", "mixedRecall"] = "embedding"
    using_re_rank: bool = False
    rerank_model: str | None = None


class SearchHitResponse(CamelModel):
    id: uuid.UUID
    q: str
    a: str | None
    dataset_id: uuid.UUID
    collection_id: uuid.UUID
    source_name: str
    score: float
```

`api/routers/health.py`：

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}
```

`api/routers/datasets.py`：

```python
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.api.deps import get_db, verify_api_key
from vector_match.api.schemas import (
    DatasetCreateRequest,
    DatasetResponse,
    DatasetUpdateRequest,
    IdResponse,
)
from vector_match.core.config import Settings, get_settings
from vector_match.services.datasets import DatasetService

router = APIRouter(prefix="/api/core/dataset", dependencies=[Depends(verify_api_key)])


@router.post("/create", response_model=IdResponse)
async def create_dataset(
    req: DatasetCreateRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    ds = await DatasetService(session).create(
        name=req.name, description=req.description, vector_model=settings.embedding_model
    )
    return IdResponse(id=ds.id)


@router.get("/list", response_model=list[DatasetResponse])
async def list_datasets(session: AsyncSession = Depends(get_db)):
    items = await DatasetService(session).list()
    return [DatasetResponse.model_validate(d) for d in items]


@router.get("/detail", response_model=DatasetResponse)
async def dataset_detail(id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    return DatasetResponse.model_validate(await DatasetService(session).detail(id))


@router.put("/update", response_model=IdResponse)
async def update_dataset(req: DatasetUpdateRequest, session: AsyncSession = Depends(get_db)):
    ds = await DatasetService(session).update(req.id, name=req.name, description=req.description)
    return IdResponse(id=ds.id)


@router.delete("/delete", response_model=IdResponse)
async def delete_dataset(id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    await DatasetService(session).delete(id)
    return IdResponse(id=id)
```

`main.py`：

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from vector_match.api.routers import datasets, health
from vector_match.core.config import get_settings
from vector_match.core.exceptions import NotFoundError, ProviderConfigError, ValidationError
from vector_match.db.session import make_engine, make_session_factory
from vector_match.providers.embedding import EmbeddingClient
from vector_match.providers.rerank import RerankClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    engine = make_engine(settings)
    app.state.settings = settings
    app.state.session_factory = make_session_factory(engine)
    app.state.embedding = EmbeddingClient(
        settings.embedding_base_url, settings.embedding_api_key, settings.embedding_model
    )
    app.state.rerank = (
        RerankClient(settings.rerank_base_url, settings.rerank_api_key, settings.rerank_model)
        if settings.rerank_base_url
        else None
    )
    yield
    await app.state.embedding.aclose()
    if app.state.rerank is not None:
        await app.state.rerank.aclose()
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="vector-match", lifespan=lifespan)

    @app.exception_handler(NotFoundError)
    async def _not_found(request: Request, exc: NotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def _validation(request: Request, exc: ValidationError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(ProviderConfigError)
    async def _provider_config(request: Request, exc: ProviderConfigError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    app.include_router(health.router)
    app.include_router(datasets.router)
    return app


app = create_app()
```

`tests/conftest.py` 追加（供全部 API 测试复用的应用与客户端 fixture）：

```python
@pytest_asyncio.fixture
async def api_app(db_session):
    from vector_match.api.deps import get_db
    from vector_match.main import create_app

    app = create_app()

    async with LifespanManager(app) as manager:
        async def _override_db():
            yield db_session

        manager.app.dependency_overrides[get_db] = _override_db
        yield manager.app


@pytest_asyncio.fixture
async def client(api_app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api_app),
        base_url="http://test",
        headers={"Authorization": "Bearer dev-key"},
    ) as c:
        yield c
```

同时在 `tests/conftest.py` 顶部补充导入：`import httpx`、`from asgi_lifespan import LifespanManager`。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && TEST_DATABASE_URL=... uv run pytest tests/test_api_app.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/vector_match/api backend/src/vector_match/main.py backend/tests/test_api_app.py
git commit -m "feat: add fastapi app skeleton with auth and dataset router"
```

---

### Task 17: collections / data 路由

**Files:**
- Create: `backend/src/vector_match/api/routers/collections.py`
- Create: `backend/src/vector_match/api/routers/data.py`
- Modify: `backend/src/vector_match/main.py`（注册两个 router）
- Test: `backend/tests/test_api_collections_data.py`

**Interfaces:**
- Consumes: `CollectionService`（Task 12）、`DataService` + `PushItem`（Task 13）、Task 16 的 schemas/deps
- Produces: collections 五个端点、data 五个端点；查询参数驼峰用 `Query(alias=...)` 实现，代码内保持蛇形

- [ ] **Step 1: 写失败测试**（`client` fixture 来自 Task 16 的 conftest）

```python
from tests.conftest import requires_db

pytestmark = requires_db


async def _make_dataset(client) -> str:
    resp = await client.post("/api/core/dataset/create", json={"name": "d"})
    return resp.json()["id"]


async def test_collection_flow(client):
    dataset_id = await _make_dataset(client)
    resp = await client.post(
        "/api/core/dataset/collection/create",
        json={"datasetId": dataset_id, "name": "手动集", "type": "virtual"},
    )
    assert resp.status_code == 200
    collection_id = resp.json()["id"]

    resp = await client.get(
        "/api/core/dataset/collection/list",
        params={"datasetId": dataset_id, "pageSize": 10, "offset": 0},
    )
    body = resp.json()
    assert body["total"] == 1 and body["list"][0]["id"] == collection_id
    assert body["list"][0]["datasetId"] == dataset_id  # 驼峰

    resp = await client.get("/api/core/dataset/collection/detail", params={"id": collection_id})
    assert resp.json()["name"] == "手动集"

    resp = await client.put(
        "/api/core/dataset/collection/update", json={"id": collection_id, "name": "手动集2"}
    )
    assert resp.status_code == 200

    resp = await client.request(
        "DELETE", "/api/core/dataset/collection/delete", json={"collectionIds": [collection_id]}
    )
    assert resp.status_code == 200
    resp = await client.get("/api/core/dataset/collection/detail", params={"id": collection_id})
    assert resp.status_code == 404


async def test_data_flow(client):
    dataset_id = await _make_dataset(client)
    resp = await client.post(
        "/api/core/dataset/collection/create",
        json={"datasetId": dataset_id, "name": "c", "type": "virtual"},
    )
    collection_id = resp.json()["id"]

    resp = await client.post(
        "/api/core/dataset/data/pushData",
        json={
            "collectionId": collection_id,
            "data": [
                {"q": "易方达蓝筹精选混合", "a": "005827", "indexes": [{"text": "易方达蓝筹"}]},
                {"q": "中欧医疗健康混合A", "a": "003095"},
            ],
        },
    )
    assert resp.status_code == 200 and resp.json() == {"insertLen": 2}

    resp = await client.get("/api/core/dataset/data/list", params={"collectionId": collection_id})
    body = resp.json()
    assert body["total"] == 2
    assert body["list"][0]["trained"] is False
    data_id = body["list"][0]["id"]

    resp = await client.get("/api/core/dataset/data/detail", params={"id": data_id})
    assert "indexes" in resp.json() and "trained" in resp.json()

    resp = await client.put(
        "/api/core/dataset/data/update", json={"dataId": data_id, "q": "改名后的基金"}
    )
    assert resp.status_code == 200
    resp = await client.get("/api/core/dataset/data/detail", params={"id": data_id})
    assert resp.json()["q"] == "改名后的基金"

    resp = await client.delete("/api/core/dataset/data/delete", params={"id": data_id})
    assert resp.status_code == 200
    resp = await client.get("/api/core/dataset/data/detail", params={"id": data_id})
    assert resp.status_code == 404


async def test_push_to_missing_collection_404(client):
    from uuid import uuid4

    resp = await client.post(
        "/api/core/dataset/data/pushData",
        json={"collectionId": str(uuid4()), "data": [{"q": "x"}]},
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && TEST_DATABASE_URL=... uv run pytest tests/test_api_collections_data.py -v`
Expected: FAIL，404/405（路由未注册）

- [ ] **Step 3: 实现**

`api/routers/collections.py`：

```python
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.api.deps import get_db, verify_api_key
from vector_match.api.schemas import (
    CollectionCreateRequest,
    CollectionDeleteRequest,
    CollectionListResponse,
    CollectionResponse,
    CollectionUpdateRequest,
    IdResponse,
)
from vector_match.services.collections import CollectionService

router = APIRouter(prefix="/api/core/dataset/collection", dependencies=[Depends(verify_api_key)])


@router.post("/create", response_model=IdResponse)
async def create_collection(req: CollectionCreateRequest, session: AsyncSession = Depends(get_db)):
    col = await CollectionService(session).create(
        dataset_id=req.dataset_id, parent_id=req.parent_id, name=req.name, type=req.type
    )
    return IdResponse(id=col.id)


@router.get("/list", response_model=CollectionListResponse)
async def list_collections(
    dataset_id: uuid.UUID = Query(alias="datasetId"),
    parent_id: uuid.UUID | None = Query(default=None, alias="parentId"),
    offset: int = Query(default=0, ge=0),
    page_size: int = Query(default=10, ge=1, le=100, alias="pageSize"),
    search_text: str | None = Query(default=None, alias="searchText"),
    session: AsyncSession = Depends(get_db),
):
    items, total = await CollectionService(session).list_page(
        dataset_id, parent_id, offset, page_size, search_text
    )
    return CollectionListResponse(
        list=[CollectionResponse.model_validate(c) for c in items], total=total
    )


@router.get("/detail", response_model=CollectionResponse)
async def collection_detail(id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    return CollectionResponse.model_validate(await CollectionService(session).detail(id))


@router.put("/update", response_model=IdResponse)
async def update_collection(req: CollectionUpdateRequest, session: AsyncSession = Depends(get_db)):
    col = await CollectionService(session).update(req.id, name=req.name)
    return IdResponse(id=col.id)


@router.delete("/delete", response_model=IdResponse)
async def delete_collections(req: CollectionDeleteRequest, session: AsyncSession = Depends(get_db)):
    await CollectionService(session).delete(req.collection_ids)
    return IdResponse(id=req.collection_ids[0])
```

`api/routers/data.py`：

```python
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from vector_match.api.deps import get_db, verify_api_key
from vector_match.api.schemas import (
    DataDetailResponse,
    DataItemResponse,
    DataListResponse,
    DataUpdateRequest,
    IdResponse,
    IndexResponse,
    PushDataRequest,
    PushDataResponse,
)
from vector_match.services.data import DataService, PushItem

router = APIRouter(prefix="/api/core/dataset/data", dependencies=[Depends(verify_api_key)])


@router.post("/pushData", response_model=PushDataResponse)
async def push_data(req: PushDataRequest, session: AsyncSession = Depends(get_db)):
    items = [
        PushItem(q=item.q, a=item.a, indexes=[idx.text for idx in item.indexes])
        for item in req.data
    ]
    n = await DataService(session).push(req.collection_id, items)
    return PushDataResponse(insert_len=n)


@router.get("/list", response_model=DataListResponse)
async def list_data(
    collection_id: uuid.UUID = Query(alias="collectionId"),
    offset: int = Query(default=0, ge=0),
    page_size: int = Query(default=10, ge=1, le=100, alias="pageSize"),
    search_text: str | None = Query(default=None, alias="searchText"),
    session: AsyncSession = Depends(get_db),
):
    items, total, trained = await DataService(session).list_page(
        collection_id, offset, page_size, search_text
    )
    return DataListResponse(
        list=[
            DataItemResponse(
                id=d.id,
                dataset_id=d.dataset_id,
                collection_id=d.collection_id,
                q=d.q,
                a=d.a,
                trained=d.id in trained,
            )
            for d in items
        ],
        total=total,
    )


@router.get("/detail", response_model=DataDetailResponse)
async def data_detail(id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    data, indexes, trained = await DataService(session).detail(id)
    return DataDetailResponse(
        id=data.id,
        dataset_id=data.dataset_id,
        collection_id=data.collection_id,
        q=data.q,
        a=data.a,
        trained=trained,
        indexes=[IndexResponse(type=i.type, text=i.text) for i in indexes],
    )


@router.put("/update", response_model=IdResponse)
async def update_data(req: DataUpdateRequest, session: AsyncSession = Depends(get_db)):
    indexes = [idx.text for idx in req.indexes] if req.indexes is not None else None
    await DataService(session).update(req.data_id, q=req.q, a=req.a, indexes=indexes)
    return IdResponse(id=req.data_id)


@router.delete("/delete", response_model=IdResponse)
async def delete_data(id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    await DataService(session).delete(id)
    return IdResponse(id=id)
```

`main.py` 中修改两处：

```python
from vector_match.api.routers import collections, data, datasets, health
```

```python
    app.include_router(health.router)
    app.include_router(datasets.router)
    app.include_router(collections.router)
    app.include_router(data.router)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && TEST_DATABASE_URL=... uv run pytest tests/test_api_collections_data.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/vector_match/api/routers backend/src/vector_match/main.py backend/tests/test_api_collections_data.py
git commit -m "feat: add collection and data routers"
```

---

### Task 18: search 路由（检索端点 e2e）

**Files:**
- Create: `backend/src/vector_match/api/routers/search.py`
- Modify: `backend/src/vector_match/main.py`（注册 search router）
- Test: `backend/tests/test_api_search.py`

**Interfaces:**
- Consumes: `SearchService` + `SearchParams`（Task 15）、`get_embedding`/`get_rerank` 依赖（Task 16）
- Produces: `POST /api/core/dataset/search` 对外端点

- [ ] **Step 1: 写失败测试**

```python
import httpx
import pytest_asyncio

from tests.conftest import requires_db
from vector_match.api.deps import get_embedding, get_rerank
from vector_match.repositories.data import DataRepository
from vector_match.services.collections import CollectionService
from vector_match.services.datasets import DatasetService

pytestmark = requires_db

DIM = 1024


def _unit_vec(i: int) -> list[float]:
    v = [0.0] * DIM
    v[i] = 1.0
    return v


class FakeEmbedding:
    async def embed(self, texts):
        return [_unit_vec(0) for _ in texts]


class FakeRerank:
    async def rerank(self, query, documents, top_n, model=None):
        return [0.5 + 0.1 * i for i in range(len(documents))]


@pytest_asyncio.fixture
async def client(api_app, db_session):
    ds = await DatasetService(db_session).create(name="d", description="")
    col = await CollectionService(db_session).create(
        dataset_id=ds.id, parent_id=None, name="基金集", type="virtual"
    )
    repo = DataRepository(db_session)
    r1, r2 = await repo.create_many([
        {"dataset_id": ds.id, "collection_id": col.id, "q": "易方达蓝筹精选混合", "a": "005827"},
        {"dataset_id": ds.id, "collection_id": col.id, "q": "中欧医疗健康混合", "a": "003095"},
    ])
    i1 = await repo.add_index(r1.id, "易方达蓝筹精选混合", type="default")
    i2 = await repo.add_index(r2.id, "中欧医疗健康混合", type="default")
    await repo.set_index_vector(i1.id, _unit_vec(0))
    await repo.set_index_vector(i2.id, _unit_vec(1))
    await repo.set_full_text_tokens(r1.id, "易方达 蓝筹 精选 混合")
    await repo.set_full_text_tokens(r2.id, "中欧 医疗 健康 混合")

    api_app.dependency_overrides[get_embedding] = lambda: FakeEmbedding()
    api_app.dependency_overrides[get_rerank] = lambda: FakeRerank()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api_app),
        base_url="http://test",
        headers={"Authorization": "Bearer dev-key"},
    ) as c:
        c.dataset_id = str(ds.id)
        c.r1_id = str(r1.id)
        yield c


async def test_search_embedding(client):
    resp = await client.post(
        "/api/core/dataset/search",
        json={"datasetId": client.dataset_id, "text": "蓝筹", "searchMode": "embedding"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["id"] == client.r1_id
    assert body[0]["sourceName"] == "基金集"
    assert body[0]["score"] > 0.99


async def test_search_fulltext(client):
    resp = await client.post(
        "/api/core/dataset/search",
        json={"datasetId": client.dataset_id, "text": "蓝筹", "searchMode": "fullTextRecall"},
    )
    assert resp.json()[0]["id"] == client.r1_id


async def test_search_mixed_with_rerank(client):
    resp = await client.post(
        "/api/core/dataset/search",
        json={
            "datasetId": client.dataset_id,
            "text": "蓝筹",
            "searchMode": "mixedRecall",
            "usingReRank": True,
            "topK": 5,
        },
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_search_missing_dataset_404(client):
    from uuid import uuid4

    resp = await client.post(
        "/api/core/dataset/search", json={"datasetId": str(uuid4()), "text": "x"}
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && TEST_DATABASE_URL=... uv run pytest tests/test_api_search.py -v`
Expected: FAIL，404（`/api/core/dataset/search` 未注册）

- [ ] **Step 3: 实现 api/routers/search.py**

```python
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
```

`main.py` 中修改两处：

```python
from vector_match.api.routers import collections, data, datasets, health, search
```

```python
    app.include_router(search.router)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && TEST_DATABASE_URL=... uv run pytest tests/test_api_search.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/vector_match/api/routers/search.py backend/src/vector_match/main.py backend/tests/test_api_search.py
git commit -m "feat: add search endpoint"
```

---

### Task 19: worker（训练执行器与常驻循环）

**Files:**
- Create: `backend/src/vector_match/worker/__init__.py`（空文件）
- Create: `backend/src/vector_match/worker/trainer.py`
- Create: `backend/src/vector_match/worker/runner.py`
- Create: `backend/src/vector_match/worker/__main__.py`
- Test: `backend/tests/test_worker.py`

**Interfaces:**
- Consumes: `TaskRepository.claim/schedule_retry/mark_done/mark_failed/reset_stale_processing`（Task 11）、`DataRepository`（Task 10）、`EmbeddingClient` + `embed_in_batches` + `EmbeddingError`（Task 7）、`to_fts_tokens`（Task 6）
- Produces: `process_batch(session_factory, embedding, settings, tasks)`；`run(settings)` 常驻循环；`python -m vector_match.worker` 入口

- [ ] **Step 1: 写失败测试**

```python
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests.conftest import TEST_DATABASE_URL, requires_db
from vector_match.core.config import Settings
from vector_match.providers.embedding import EmbeddingError
from vector_match.repositories.collections import CollectionRepository
from vector_match.repositories.data import DataRepository
from vector_match.repositories.datasets import DatasetRepository
from vector_match.repositories.tasks import TaskRepository
from vector_match.services.data import DataService, PushItem
from vector_match.worker.trainer import process_batch

pytestmark = requires_db


class FakeEmbedding:
    def __init__(self, fail: bool = False):
        self._fail = fail

    async def embed(self, texts):
        if self._fail:
            raise EmbeddingError("boom")
        return [[0.1] * 1024 for _ in texts]


@pytest_asyncio.fixture
async def worker_env():
    """worker 自行开会话并 commit，不能用回滚夹具；测试后清表。"""
    engine = create_async_engine(TEST_DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    async with engine.begin() as conn:
        for table in ("training_tasks", "data_indexes", "dataset_data", "collections", "datasets"):
            await conn.execute(text(f"DELETE FROM {table}"))
    await engine.dispose()


async def _seed(worker_env) -> None:
    async with worker_env() as session:
        ds = await DatasetRepository(session).create(name="d", description="", vector_model="m")
        col = await CollectionRepository(session).create(
            dataset_id=ds.id, parent_id=None, name="c", type="virtual"
        )
        await session.commit()
        await DataService(session).push(
            col.id, [PushItem(q="易方达蓝筹精选混合", a="005827", indexes=["易方达蓝筹"])]
        )


async def _claim(worker_env):
    async with worker_env() as session:
        tasks = await TaskRepository(session).claim(10)
        await session.commit()
        return tasks


async def test_process_batch_trains(worker_env):
    await _seed(worker_env)
    tasks = await _claim(worker_env)
    assert len(tasks) == 1

    await process_batch(worker_env, FakeEmbedding(), Settings(worker_concurrency=2), tasks)

    async with worker_env() as session:
        assert (await TaskRepository(session).get(tasks[0].id)).status == "done"
        data_repo = DataRepository(session)
        data = await data_repo.get(tasks[0].data_id)
        assert data.full_text_tokens != ""
        indexes = await data_repo.list_valid_indexes(data.id)
        assert len(indexes) == 2
        assert all(i.vector is not None for i in indexes)
        assert data.id in await data_repo.list_trained_data_ids([data.id])


async def test_process_batch_retries_on_embedding_error(worker_env):
    await _seed(worker_env)
    tasks = await _claim(worker_env)

    await process_batch(worker_env, FakeEmbedding(fail=True), Settings(), tasks)

    async with worker_env() as session:
        task = await TaskRepository(session).get(tasks[0].id)
        assert task.status == "pending"
        assert task.attempts == 1
        assert "boom" in task.last_error


async def test_process_batch_marks_deleted_data(worker_env):
    await _seed(worker_env)
    tasks = await _claim(worker_env)
    async with worker_env() as session:
        await DataRepository(session).soft_delete_many([tasks[0].data_id])
        await session.commit()

    await process_batch(worker_env, FakeEmbedding(), Settings(), tasks)

    async with worker_env() as session:
        task = await TaskRepository(session).get(tasks[0].id)
        assert task.status == "error" and task.last_error == "data deleted"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && TEST_DATABASE_URL=... uv run pytest tests/test_worker.py -v`
Expected: FAIL，`ModuleNotFoundError: vector_match.worker`

- [ ] **Step 3: 实现**

`worker/trainer.py`：

```python
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vector_match.core.config import Settings
from vector_match.core.text import to_fts_tokens
from vector_match.db.models import TrainingTask
from vector_match.providers.embedding import EmbeddingClient, EmbeddingError, embed_in_batches
from vector_match.repositories.data import DataRepository
from vector_match.repositories.tasks import TaskRepository


async def process_batch(
    session_factory: async_sessionmaker[AsyncSession],
    embedding: EmbeddingClient,
    settings: Settings,
    tasks: list[TrainingTask],
) -> None:
    """对一批已 claim 的任务执行训练：分词 + 批量 embedding + 回写向量。"""
    items: list[tuple[uuid.UUID, uuid.UUID, list[tuple[uuid.UUID, str]], str]] = []
    async with session_factory() as session:
        task_repo = TaskRepository(session)
        data_repo = DataRepository(session)
        for t in tasks:
            data = await data_repo.get(t.data_id)
            if data is None:
                await task_repo.mark_failed(t.id, "data deleted")
                continue
            indexes = await data_repo.list_valid_indexes(data.id, only_untrained=True)
            if not indexes:
                await task_repo.mark_done(t.id)
                continue
            items.append(
                (t.id, data.id, [(i.id, i.text) for i in indexes], f"{data.q} {data.a or ''}")
            )
        await session.commit()

    if not items:
        return

    texts = [text for _, _, pairs, _ in items for _, text in pairs]
    try:
        vectors = await embed_in_batches(embedding, texts, concurrency=settings.worker_concurrency)
    except EmbeddingError as exc:
        async with session_factory() as session:
            task_repo = TaskRepository(session)
            for task_id, *_ in items:
                await task_repo.schedule_retry(task_id, str(exc), settings.worker_max_attempts)
            await session.commit()
        return

    pos = 0
    async with session_factory() as session:
        task_repo = TaskRepository(session)
        data_repo = DataRepository(session)
        for task_id, data_id, pairs, fts_source in items:
            for index_id, _ in pairs:
                await data_repo.set_index_vector(index_id, vectors[pos])
                pos += 1
            await data_repo.set_full_text_tokens(data_id, to_fts_tokens(fts_source))
            await task_repo.mark_done(task_id)
        await session.commit()
```

`worker/runner.py`：

```python
import asyncio
import signal

from vector_match.core.config import Settings
from vector_match.db.session import make_engine, make_session_factory
from vector_match.providers.embedding import EmbeddingClient
from vector_match.repositories.tasks import TaskRepository
from vector_match.worker.trainer import process_batch


async def run(settings: Settings) -> None:
    engine = make_engine(settings)
    session_factory = make_session_factory(engine)
    embedding = EmbeddingClient(
        settings.embedding_base_url, settings.embedding_api_key, settings.embedding_model
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    try:
        async with session_factory() as session:
            await TaskRepository(session).reset_stale_processing()
            await session.commit()

        while not stop.is_set():
            async with session_factory() as session:
                tasks = await TaskRepository(session).claim(settings.worker_batch_size)
                await session.commit()
            if not tasks:
                try:
                    await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_interval)
                except TimeoutError:
                    pass
                continue
            await process_batch(session_factory, embedding, settings, tasks)
    finally:
        await embedding.aclose()
        await engine.dispose()
```

`worker/__main__.py`：

```python
import asyncio

from vector_match.core.config import get_settings
from vector_match.worker.runner import run


def main() -> None:
    asyncio.run(run(get_settings()))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && TEST_DATABASE_URL=... uv run pytest tests/test_worker.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/vector_match/worker backend/tests/test_worker.py
git commit -m "feat: add training worker with pg queue"
```

---

### Task 20: Docker 化与部署文件

**Files:**
- Create: `backend/Dockerfile`、`backend/.dockerignore`
- Create: `docker-compose.yml`（仓库根目录）
- Create: `.env.example`（仓库根目录）
- Modify: `README.md`（仓库根目录，写快速上手）

**Interfaces:**
- Produces: `docker compose up -d --build` 一键起 postgres + app + worker

- [ ] **Step 1: 写 backend/Dockerfile**

```dockerfile
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./
RUN uv sync --frozen --no-dev

CMD ["uv", "run", "uvicorn", "vector_match.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: 写 backend/.dockerignore**

```
.venv
__pycache__
tests
.env
*.pyc
.pytest_cache
.ruff_cache
```

- [ ] **Step 3: 写根目录 docker-compose.yml**

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: vector_match
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 10
    ports:
      - "5432:5432"

  app:
    build: ./backend
    env_file: .env
    environment:
      DATABASE_URL: postgresql+psycopg://postgres:postgres@postgres:5432/vector_match
    command: sh -c "uv run alembic upgrade head && uv run uvicorn vector_match.main:app --host 0.0.0.0 --port 8000"
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "8000:8000"

  worker:
    build: ./backend
    env_file: .env
    environment:
      DATABASE_URL: postgresql+psycopg://postgres:postgres@postgres:5432/vector_match
    command: uv run python -m vector_match.worker
    depends_on:
      postgres:
        condition: service_healthy

volumes:
  pgdata:
```

- [ ] **Step 4: 写根目录 .env.example**（面向宿主机本地开发；compose 会用 `environment:` 覆盖 DATABASE_URL 指向容器网络）

```
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/vector_match
POSTGRES_PASSWORD=postgres

API_KEYS=dev-key

EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_API_KEY=
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIM=1024

RERANK_BASE_URL=https://api.siliconflow.cn/v1
RERANK_API_KEY=
RERANK_MODEL=BAAI/bge-reranker-v2-m3

WORKER_POLL_INTERVAL=2
WORKER_BATCH_SIZE=32
WORKER_CONCURRENCY=4
WORKER_MAX_ATTEMPTS=5

RECALL_LIMIT=60
RERANK_CANDIDATES=30
```

- [ ] **Step 5: 写根目录 README.md**

````markdown
# vector-match

通用化文本匹配服务：语义检索 / 全文检索 / 混合检索 + 重排。适用于基金名称匹配基金 ID、实体名称标准化、短文本相似匹配等场景。检索引擎参考 FastGPT 知识库设计。

## 架构

- `app`：FastAPI，REST API（`/api/core/dataset/...`）
- `worker`：训练进程，从 PG 队列消费任务，调 embedding API 写入向量
- `postgres`：pgvector，承载业务数据 + 向量（HNSW）+ 全文检索 + 任务队列

## 快速开始

```bash
cp .env.example .env   # 填入 EMBEDDING_API_KEY / RERANK_API_KEY
docker compose up -d --build
curl http://localhost:8000/health
```

## 本地开发

```bash
cd backend
uv sync
uv run pytest                    # 单测（DB 测试自动跳过）
docker run -d --name vm-test-pg -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=vector_match_test -p 5432:5432 pgvector/pgvector:pg16
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/vector_match_test \
  uv run pytest                  # 全部测试
uv run ruff check
uv run uvicorn vector_match.main:app --reload
```

## API 一览

除 `/health` 外均需 `Authorization: Bearer <API_KEYS 之一>`。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/core/dataset/create` | 创建知识库 |
| GET | `/api/core/dataset/list` | 知识库列表 |
| GET | `/api/core/dataset/detail?id=` | 知识库详情 |
| PUT | `/api/core/dataset/update` | 更新知识库 |
| DELETE | `/api/core/dataset/delete?id=` | 删除知识库（级联软删） |
| POST | `/api/core/dataset/collection/create` | 创建集合（`folder`/`virtual`） |
| GET | `/api/core/dataset/collection/list` | 集合分页列表 |
| GET | `/api/core/dataset/collection/detail?id=` | 集合详情 |
| PUT | `/api/core/dataset/collection/update` | 更新集合 |
| DELETE | `/api/core/dataset/collection/delete` | 删除集合（body: `collectionIds`） |
| POST | `/api/core/dataset/data/pushData` | 批量推送数据（≤200 条/批） |
| GET | `/api/core/dataset/data/list` | 数据分页列表 |
| GET | `/api/core/dataset/data/detail?id=` | 数据详情（含索引与训练状态） |
| PUT | `/api/core/dataset/data/update` | 更新数据（触发重建索引） |
| DELETE | `/api/core/dataset/data/delete?id=` | 删除数据 |
| POST | `/api/core/dataset/search` | 检索（embedding/fullTextRecall/mixedRecall + 重排） |

## 检索示例

```bash
curl -X POST http://localhost:8000/api/core/dataset/search \
  -H "Authorization: Bearer dev-key" \
  -H "Content-Type: application/json" \
  -d '{"datasetId": "<库ID>", "text": "易方达蓝筹", "searchMode": "mixedRecall", "usingReRank": true, "topK": 5}'
```

冒烟验证：`python scripts/smoke_fund_match.py`（需服务已启动且 embedding 配置可用）。
````

- [ ] **Step 6: 构建验证**

```bash
cp .env.example .env
docker compose build
docker compose config --quiet
```

Expected: 构建成功；`config` 无输出（compose 文件合法）。镜像构建成功后可选执行 `docker compose up -d` 并 `curl localhost:8000/health` 验证（需要有效 EMBEDDING_API_KEY 才能完整跑通检索，健康检查不需要）。

- [ ] **Step 7: Commit**

```bash
git add backend/Dockerfile backend/.dockerignore docker-compose.yml .env.example README.md
git commit -m "feat: add docker deployment and readme"
```

---

### Task 21: smoke 脚本与最终验证

**Files:**
- Create: `scripts/smoke_fund_match.py`（仓库根目录）

**Interfaces:**
- Produces: 端到端冒烟验证脚本

- [ ] **Step 1: 写 scripts/smoke_fund_match.py**

```python
"""端到端冒烟：灌入示例基金数据，验证三种检索模式。

用法：先启动服务（docker compose up -d），再执行 python scripts/smoke_fund_match.py
环境变量：BASE_URL（默认 http://localhost:8000）、API_KEY（默认 dev-key）
"""

import os
import sys
import time

import httpx

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
API_KEY = os.environ.get("API_KEY", "dev-key")
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

FUNDS = [
    {"q": "易方达蓝筹精选混合", "a": "005827", "indexes": [{"text": "易方达蓝筹"}]},
    {"q": "中欧医疗健康混合A", "a": "003095", "indexes": [{"text": "中欧医疗"}]},
    {"q": "招商中证白酒指数A", "a": "161725", "indexes": [{"text": "招商白酒"}]},
    {"q": "华夏上证50ETF联接A", "a": "001051", "indexes": [{"text": "上证50"}]},
    {"q": "景顺长城新兴成长混合A", "a": "260108", "indexes": [{"text": "景顺成长"}]},
    {"q": "富国天惠成长混合A", "a": "161005", "indexes": [{"text": "富国天惠"}]},
]


def main() -> int:
    client = httpx.Client(base_url=BASE_URL, headers=HEADERS, timeout=30)

    ds = client.post("/api/core/dataset/create", json={"name": f"smoke-基金库-{int(time.time())}"}).json()
    dataset_id = ds["id"]
    col = client.post(
        "/api/core/dataset/collection/create",
        json={"datasetId": dataset_id, "name": "smoke集", "type": "virtual"},
    ).json()
    collection_id = col["id"]
    resp = client.post(
        "/api/core/dataset/data/pushData", json={"collectionId": collection_id, "data": FUNDS}
    )
    assert resp.status_code == 200 and resp.json()["insertLen"] == len(FUNDS), resp.text
    print(f"已推送 {len(FUNDS)} 条数据，等待训练...")

    deadline = time.time() + 120
    while time.time() < deadline:
        body = client.get(
            "/api/core/dataset/data/list", params={"collectionId": collection_id, "pageSize": 50}
        ).json()
        if body["total"] == len(FUNDS) and all(item["trained"] for item in body["list"]):
            break
        time.sleep(2)
    else:
        print("FAIL 训练超时（120s）")
        return 1
    print("训练完成，开始检索验证")

    cases = [
        ("语义检索「易方达蓝筹」", {"datasetId": dataset_id, "text": "易方达蓝筹", "searchMode": "embedding"}, "005827"),
        ("全文检索「005827」", {"datasetId": dataset_id, "text": "005827", "searchMode": "fullTextRecall"}, "005827"),
        ("混合+重排「医疗基金」", {"datasetId": dataset_id, "text": "医疗基金", "searchMode": "mixedRecall", "usingReRank": True}, "003095"),
    ]
    ok = True
    for title, payload, expect_code in cases:
        hits = client.post("/api/core/dataset/search", json=payload).json()
        top = hits[0] if hits else None
        passed = top is not None and top["a"] == expect_code
        ok = ok and passed
        if top:
            print(f"{'PASS' if passed else 'FAIL'} {title} -> {top['q']} ({top['a']}) score={top['score']:.4f}")
        else:
            print(f"FAIL {title} -> 无结果")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 全量测试与 lint 最终验证**

```bash
cd backend
uv run ruff check
uv run pytest                                    # 纯单测
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/vector_match_test uv run pytest
```

Expected: ruff 无错误；两轮 pytest 全部 PASS（第二轮含全部集成测试）。

- [ ] **Step 3: 冒烟（需要真实 embedding API）**

```bash
cp .env.example .env   # 填入真实 EMBEDDING_API_KEY / RERANK_API_KEY
docker compose up -d --build
python scripts/smoke_fund_match.py
```

Expected: 输出 3 个 PASS，退出码 0。

- [ ] **Step 4: Commit**

```bash
git add scripts/smoke_fund_match.py
git commit -m "feat: add end-to-end smoke script"
```
