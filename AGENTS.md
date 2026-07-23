# AGENTS.md

本文件为 AI 编码代理提供项目级工作指南。

## 项目概览

vector-match：通用短文本匹配服务（语义/全文/混合检索 + 重排），检索引擎与 Web 界面均参考 FastGPT 知识库模块并按 YAGNI 裁剪（无文件上传、无 QA 拆分、无图片、无多租户）。

## 仓库结构

- `backend/`：Python 3.13 + FastAPI + SQLAlchemy 2.x(async) + PostgreSQL/pgvector，包管理用 `uv`
  - `src/vector_match/api/routers/`：HTTP 路由；`api/schemas.py`：Pydantic v2 schema（**JSON 序列化为 camelCase**）
  - `services/` 业务逻辑、`repositories/` 数据访问、`db/models.py` ORM、`worker/` 训练进程、`providers/` embedding/rerank 客户端
  - `alembic/` 迁移
- `web/`：Next.js 16（App Router）+ TypeScript + Tailwind v4 + shadcn/ui + TanStack Query
  - `app/datasets/`：知识库管理页面（列表 / 详情壳 / collections / data / search / settings）；`app/login`、`app/register`、`app/settings/users`：认证与用户管理页
  - `app/api/proxy/[...path]/route.ts`：BFF 代理，从 httpOnly Cookie `session` 读 JWT 作为 Bearer 转发到 `${BACKEND_URL}/api/*`；`app/api/auth/login|logout/route.ts`：写/清 Cookie
  - `proxy.ts`：Next 16 路由守卫（middleware.ts 已废弃更名），未登录访问受护页面跳 /login
  - `lib/api.ts` 按域分组的 API client、`lib/types.ts` 与后端 camelCase 对齐的类型、`hooks/` react-query hooks
  - `web/AGENTS.md`：Next.js 16 专项提醒（params/searchParams 为 Promise、useSearchParams 需 Suspense 等）
- `docker-compose.yml`：postgres / app / worker / web 四服务
- `docs/superpowers/specs/2026-07-16-vector-match-design.md`：后端设计文档（API 表、数据模型、检索流程）；`2026-07-21-auth-rbac-design.md`：认证与权限设计

## 关键约定

- **认证**：JWT。`POST /api/auth/login` 拿 token；除 `/health`、`/api/auth/register|login` 外全部 `Authorization: Bearer <jwt>`（`JWT_SECRET` 环境变量，必填）。前端不持 token：登录由 BFF 写 httpOnly Cookie，代理转发时注入
- **授权**：站点级角色 `superadmin/admin/user`（`users.role`），新用户注册默认 `user` 且 `is_approved=false`，登录会被拒绝并提示“账号正在审核中”；只有 `superadmin` 可审批用户、修改角色。`admin`/`superadmin` 可创建知识库，普通用户只能被授权为成员。知识库成员角色 `owner/editor/viewer`（`dataset_members` 表），`owner` 仅限创建者/站点管理员；`editor` 只能操作数据（push/update/delete），不能管理集合、成员与设置。依赖 `require_dataset_access` / `require_collection_access` / `require_data_access` 按端点族解析 id 后判定；dataset detail 响应含 `myRole` 与 `creatorId` 供前端权限化 UI
- **API 形状**：字段 camelCase；分页参数 `offset`/`pageSize`（≤100）；collection 删除走 body `{collectionIds}`，dataset/data 删除走 `?id=`；错误体统一 `{detail: string}`（422 时 detail 为数组）
- **数据流**：pushData（≤200 条/批）→ worker 异步训练 → `trained=true` 后才可检索；folder 集合不能 pushData（仅 virtual）
- **Embedding**：`EMBEDDING_DIM` 由 ORM/迁移直接读 `os.environ`，不经 pydantic-settings；compose 之外运行必须显式 export

## 常用命令

后端（`backend/`）：`uv sync`、`uv run pytest`（DB 测试需 `TEST_DATABASE_URL` 指向独立测试库，如 `postgresql+psycopg://postgres:postgres@localhost:5432/vector_match_test`；库名必须含 "test"，部分测试会物理清表，严禁指向开发库 `vector_match`）、`uv run ruff check`、`uv run alembic upgrade head`

前端（`web/`）：`npm run dev`、`npx tsc --noEmit`、`npm run lint`、`npm run build`

全栈：`docker compose up -d --build`（web: http://localhost:3000，api: :8000）

## 环境注意事项

- 本机测试 pg 容器 `vm-test-pg`（5432）与 compose postgres 端口冲突，二者不可同时运行
- Next.js 16 `output: "standalone"` 下不要用 `next start` 验证 route handler，用 `node .next/standalone/server.js`（需 HOSTNAME/PORT 环境变量）
- 写 web 代码前先看 `web/AGENTS.md` 的 Next 16 breaking changes 提醒
