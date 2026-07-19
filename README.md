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

注意：`EMBEDDING_DIM` 由 ORM 模型与建表迁移直接读取进程环境变量（`os.environ`），不经 `.env` 文件 / pydantic-settings；在 docker compose 之外运行时，必须将其导出为真实环境变量（如 `export EMBEDDING_DIM=1024`）。

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
