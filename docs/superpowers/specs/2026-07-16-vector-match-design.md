# vector-match 设计文档

日期：2026-07-16
状态：已确认

## 1. 背景与目标

vector-match 是一个通用化文本匹配服务，核心场景是**短文本词条匹配**：例如基金名称匹配基金 ID、实体名称标准化、两段文本相似匹配并返回相似度得分。检索能力参考 [FastGPT 知识库引擎](https://doc.fastgpt.cn/zh-CN/guide/dataset/dataset_engine)，支持：

- 语义检索（向量相似度）
- 全文检索（关键词命中）
- 混合检索（双路召回 + RRF 融合）
- 结果重排（rerank 模型二次排序）

接口风格参考 [FastGPT OpenAPI 知识库部分](https://doc.fastgpt.cn/zh-CN/openapi/dataset)，但不追求 wire 级兼容。

**本文档范围**：仅覆盖后端服务，实现代码全部位于 `backend/` 目录。前端在后端实现完成后另行设计，不在本规格内。

### 明确不做（YAGNI）

- 文件上传解析入库（PDF/CSV/链接抓取等）
- QA 拆分、问题优化（LLM 查询扩展）
- 图片检索
- 同一实例多 embedding 模型混用
- 计费、权限分级、多租户

## 2. 总体架构

三个组件，Docker Compose 编排：

- `app`：FastAPI 服务，对外 REST API。写请求落训练队列后立即返回。
- `worker`：与 app 同一镜像、不同启动命令（`python -m vector_match.worker`），轮询队列执行训练任务（分词 + 调 embedding API + 写向量）。
- `postgres`：官方 `pgvector/pgvector:pg16` 镜像，同时承担业务数据、向量检索、全文检索、任务队列四个角色。

**队列用 PG 实现，不引入 Redis**：队列表 + `SELECT ... FOR UPDATE SKIP LOCKED` 出队。理由：数据行与任务可同事务提交，不会丢任务；几万~几十万级任务量对 PG 毫无压力；少一个中间件。队列访问收敛在 repository 层接口后，未来可换实现。

**异步写链路的取舍**：初始化导入几万条时，吞吐瓶颈在 embedding API（批量接口 + 并发调用解决），不在队列。数据在训练完成前不可检索（最终一致），与 FastGPT 语义一致。

### 技术栈

- Python 3.13，uv 管理依赖
- FastAPI + uvicorn
- SQLAlchemy 2.x + pgvector-python + psycopg3
- httpx（异步调用 OpenAI 兼容 API）
- pydantic-settings（环境变量配置）
- jieba（中文分词）
- Alembic（schema 迁移）
- pytest + ruff

### 代码结构

```
backend/
  pyproject.toml      # 现有根目录脚手架迁移至此
  Dockerfile
  src/vector_match/
    api/          # 路由、API key 鉴权、请求/响应模型
    core/         # 配置、异常、日志
    db/           # 引擎、会话、ORM 模型
    repositories/ # SQL 数据访问（含队列出入队）
    services/     # 业务编排（库/集合/数据/检索/级联删除）
    providers/    # embedding / rerank 客户端（OpenAI 兼容）
    worker/       # 队列消费与训练任务执行
  tests/
docker-compose.yml    # 仓库根目录，编排 postgres + app + worker
```

## 3. 数据模型

全部存 PostgreSQL。统一约定：

- 每张表都有 `create_time`、`update_time`、`isvalid`（smallint，`1` 有效 / `0` 无效）
- **不建外键约束**，关联字段（`dataset_id` 等）为普通字段 + 普通 B-tree 索引
- 删除一律软删除（`isvalid = 0`），级联软删由 service 层实现
- 所有查询带 `isvalid = 1` 过滤

### datasets（知识库）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid | 主键 |
| name | text | 库名 |
| description | text | 介绍，默认空串 |
| vector_model | text | 记录所用 embedding 模型（见下注） |

### collections（集合）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid | 主键 |
| dataset_id | uuid | 所属库 |
| parent_id | uuid 可空 | 父级集合，支持目录结构 |
| name | text | 集合名 |
| type | text | `folder`（目录）/ `virtual`（手动集合） |

### dataset_data（数据）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid | 主键 |
| dataset_id | uuid | 所属库（冗余，便于按库检索） |
| collection_id | uuid | 所属集合 |
| key_id | varchar(128) 可空 | 外部源主键（如 fund_id/company_id），NULL=手动 push 数据 |
| source_updatetime | timestamptz 可空 | 外部源更新时间，仅作同步判定元数据 |
| q | text | 主要数据（如基金名称） |
| a | text 可空 | 辅助数据（如基金代码/ID） |
| full_text_tokens | text | jieba 分词结果，空格分隔；训练时由 worker 回写，建 GIN 索引 |

约束：`(dataset_id, key_id)` 在 `isvalid = 1 AND key_id IS NOT NULL` 条件下唯一。

### data_indexes（多向量索引）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid | 主键 |
| data_id | uuid | 所属数据 |
| type | text | `default` / `custom` |
| text | text | 索引文本 |
| vector | vector(N) | pgvector，HNSW 索引（cosine：`vector_cosine_ops`） |

规则：每条数据至少一个 default 索引（文本 = `q`）；最多 5 个 custom 索引（别名、简称等）。任一向量命中即召回该数据，同一数据取最高分。

### training_tasks（训练队列）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | uuid | 主键 |
| data_id | uuid | 关联数据 |
| status | text | `pending` / `processing` / `done` / `error` |
| attempts | int | 已尝试次数，默认 0 |
| next_retry_at | timestamptz | 下次可执行时间 |
| last_error | text | 最近一次错误信息 |

### 关于 embedding 模型的简化

embedding 模型为**部署级配置**：一个实例一个模型，向量维度在建表迁移时固定。`datasets.vector_model` 仅作记录。换模型需迁移重建向量列；要多模型就再部署一个实例。rerank 模型无存储影响，每次检索请求可单独指定。

## 4. 写链路与 worker

### 推送数据

`POST /api/core/dataset/data/pushData`，参数 `{collectionId, data: [{q, a?, keyId?, updatetime?, indexes?}]}`，每批 ≤ 200 条。`updatetime` 必须配合 `keyId` 使用；naive datetime 按 UTC 处理。每条数据在一个事务内写入 `dataset_data` 行（此时 `full_text_tokens` 为空）+ 一条 `pending` 训练任务，接口立即返回 `{insertLen, updateLen, skipLen}`。

- 无 `keyId`：纯插入。
- 有 `keyId`：按 `(dataset_id, key_id)` 查找有效行。不存在则插入；存在则比对 `q`、`a`、`indexes` 文本集合，内容完全相同则 skip（仅当 `updatetime` 变化时更新该时间戳），有变化则整行重建索引并产生训练任务。

**训练完成前数据不可检索**：索引行不存在且 `full_text_tokens` 为空，两路召回都自然命中不到。

### worker 循环

1. `SELECT ... WHERE status='pending' AND next_retry_at <= now() ORDER BY id LIMIT N FOR UPDATE SKIP LOCKED` 批量出队，置 `processing`
2. 每条数据：jieba 对 `q` + `a` 分词，回写 `full_text_tokens`；收集全部索引文本（default + custom）
3. 整批合并调一次批量 embedding API → 写入 `data_indexes` → 任务置 `done`
4. 失败：`attempts + 1`，`next_retry_at` 指数退避；超过 `WORKER_MAX_ATTEMPTS`（默认 5）置 `error`，数据保持不可检索，可修复后重置任务重试

并发模型：asyncio + httpx，轮询间隔、出队批量、API 并发数均可配置；优雅退出。worker 防御性跳过已删除数据的任务。

### 更新数据

`PUT /api/core/dataset/data/update` 修改 q/a/索引 → 旧索引行置 `isvalid = 0` → 生成新训练任务，**整条重建**该数据的索引（不做 FastGPT 的按 dataId 差量更新——词条很短，embedding 成本可忽略）。

### 删除与级联

- 删数据 → 连同其索引行软删，pending 任务置 `error`
- 删集合 → 连同其数据、索引、待训练任务
- 删库 → 级联下属全部
- 软删向量行仍占 HNSW 空间，运维上定期 `VACUUM`，v1 不做自动清理

## 5. 检索管线

入口 `POST /api/core/dataset/search`，参数：

| 参数 | 说明 | 默认 |
| --- | --- | --- |
| datasetId | 知识库 ID | 必填 |
| text | 查询文本 | 必填 |
| topK | 返回条数 | 10 |
| similarity | 最低相关度 0~1 | 0 |
| searchMode | `embedding` / `fullTextRecall` / `mixedRecall` | `embedding` |
| usingReRank | 是否重排 | false |
| rerankModel | 重排模型 | 服务端默认配置 |

管线五步：

1. **语义召回**：查询文本经 embedding API 向量化 → `data_indexes` 上按 dataset + `isvalid = 1` 过滤做 HNSW cosine 检索，取候选 N 条（`N = max(topK, 60)`，即 `RECALL_LIMIT`）→ 按 `data_id` 合并，同一数据取最高分（得分 = 1 − cosine 距离）
2. **全文召回**：查询文本 jieba 分词 → `plainto_tsquery('simple', ...)` 匹配 `full_text_tokens`，按 `ts_rank` 取候选 N 条
3. **RRF 融合**（仅混合模式）：两路结果按 `score = Σ 1/(60 + rank)` 融合排序
4. **重排**（可选）：融合后取前 M 条（`RERANK_CANDIDATES`，默认 30）调 rerank API，得 0~1 相关度得分，按重排得分重排
5. **过滤裁剪**：`similarity` 阈值过滤 → 按 `topK` 截断

**得分口径与 similarity 生效条件**（与 FastGPT 一致）：

| 模式 | 得分 | similarity 过滤 |
| --- | --- | --- |
| 语义 | cosine 相似度 0~1 | 生效 |
| 全文 | ts_rank 按本批结果最大值归一化到 0~1 | 不生效 |
| 混合（不重排） | RRF 得分 | 不生效 |
| 任意 + 重排 | rerank 得分 0~1 | 生效 |

返回：`[{id, q, a, datasetId, collectionId, sourceName, score, keyId?}]`（`sourceName` 取集合名，`keyId` 仅外部数据有值）。

## 6. API 一览

路径沿用 FastGPT `/api/core/dataset/...` 风格。统一约定：

- 鉴权：`Authorization: Bearer <key>`，密钥配置在服务端 `API_KEYS` 环境变量（支持多个），中间件统一校验
- 响应：标准 HTTP 状态码 + FastAPI 默认错误体，成功直接返回数据，不套 `{code, statusText, message, data}` 信封
- **命名：对内蛇形、对外驼峰**——Python 代码内部一律 snake_case，JSON 报文 camelCase，用 pydantic v2 `alias_generator=to_camel` + `populate_by_name=True` 自动转换

### 知识库

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/core/dataset/create` | `{name, description?}` → id |
| GET | `/api/core/dataset/list` | 全部库 |
| GET | `/api/core/dataset/detail?id=` | 详情 |
| PUT | `/api/core/dataset/update` | `{id, name?, description?}` |
| DELETE | `/api/core/dataset/delete?id=` | 软删，级联 |

### 集合

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/core/dataset/collection/create` | `{datasetId, parentId?, name, type}` |
| GET | `/api/core/dataset/collection/list` | `datasetId, parentId, offset, pageSize, searchText` 分页 |
| GET | `/api/core/dataset/collection/detail?id=` | 详情 |
| PUT | `/api/core/dataset/collection/update` | `{id, name?}` |
| DELETE | `/api/core/dataset/collection/delete` | `{collectionIds: [...]}`，级联 |

### 数据

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/core/dataset/data/pushData` | `{collectionId, data: [{q, a?, keyId?, updatetime?, indexes?}]}`，每批 ≤200。keyId 用于外部源 upsert：内容无变化则 skip，有变化则 update；不带 keyId 走纯插入 → `{insertLen, updateLen, skipLen}` |
| GET | `/api/core/dataset/data/list` | `collectionId, offset, pageSize, searchText` 分页 |
| GET | `/api/core/dataset/data/detail?id=` | 含索引与训练状态 |
| PUT | `/api/core/dataset/data/update` | `{dataId, q?, a?, indexes?}`，触发重建 |
| DELETE | `/api/core/dataset/data/delete?id=` | 软删 |
| DELETE | `/api/core/dataset/data/deleteByKey` | `{collectionId, keyIds: [...]}`（≤200）按外部主键软删，幂等，返回 `{deleteLen}` |

### 检索与其他

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/core/dataset/search` | 见第 5 节 |
| GET | `/health` | 健康检查 |

## 7. 模型提供者

`providers/` 下两个客户端，均走 OpenAI 兼容 HTTP 接口：

- **EmbeddingClient**：`POST {EMBEDDING_BASE_URL}/embeddings`，支持批量输入
- **RerankClient**：`POST {RERANK_BASE_URL}/rerank`（Jina / 硅基流动等兼容格式），输入 query + documents，返回 0~1 相关度

调用方只依赖抽象接口，便于 mock 测试和未来换实现。

## 8. 配置

环境变量（pydantic-settings，支持 `.env`）：

| 变量 | 说明 |
| --- | --- |
| `DATABASE_URL` | PG 连接串 |
| `API_KEYS` | API 密钥，逗号分隔 |
| `EMBEDDING_BASE_URL` / `EMBEDDING_API_KEY` / `EMBEDDING_MODEL` / `EMBEDDING_DIM` | embedding 服务 |
| `RERANK_BASE_URL` / `RERANK_API_KEY` / `RERANK_MODEL` | rerank 服务 |
| `WORKER_POLL_INTERVAL` / `WORKER_BATCH_SIZE` / `WORKER_CONCURRENCY` / `WORKER_MAX_ATTEMPTS` | worker 调参 |
| `RECALL_LIMIT`（默认 60）/ `RERANK_CANDIDATES`（默认 30）/ 默认 `topK`（10） | 检索默认 |

## 9. 部署

- 单个多阶段 Dockerfile（位于 `backend/`，uv 安装依赖），app 与 worker 共用镜像、不同启动命令
- 仓库根目录 `docker-compose.yml`：`postgres`（`pgvector/pgvector:pg16`）+ `app` + `worker`，含健康检查与数据卷
- Alembic 管理 schema 迁移（含 HNSW、GIN 索引），首次启动 `alembic upgrade head`

## 10. 测试

- 单测：RRF 融合、jieba 分词、provider 客户端（mock httpx）、级联软删逻辑
- 集成测试：测试 PG（compose 或 testcontainers）跑通全链路：建库 → 建集合 → 推送 → 训练 → 三种模式检索 → 更新 → 删除；模型 provider 一律 mock
- smoke 脚本：灌入示例基金名称数据 → `/api/core/dataset/search` 验证匹配效果
- ruff 做 lint + format
