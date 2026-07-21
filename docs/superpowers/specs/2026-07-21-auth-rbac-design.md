# 登录系统与按知识库授权的权限系统设计文档

日期：2026-07-21
状态：已确认

## 1. 背景与目标

vector-match 当前无任何用户/权限概念：认证仅靠共享静态 API Key（`verify_api_key`，`backend/src/vector_match/api/deps.py`），前端 BFF 代理硬编码注入 `Authorization: Bearer ${API_KEY}`，所有调用者地位等同。前设计文档中的"权限分级"属于当时明确的 YAGNI 项，现需求变更，本文档定义登录系统与按知识库授权的权限系统。

### 已确认的决策

| 决策点 | 结论 |
| --- | --- |
| 权限粒度 | 按知识库授权：`owner / editor / viewer` 三级角色 + 站点级 `superuser` |
| 认证方式 | 全面切换 JWT，移除静态 API Key（外部脚本/集成需改造走登录） |
| 用户来源 | 开放注册，注册后为普通用户（无任何知识库权限、非 superuser） |
| 会话保持 | httpOnly Cookie 承载 JWT，由前端 BFF 代理读取并转为 Bearer 转发，浏览器不持 token |

### 明确不做（YAGNI）

- 权限点级别的 RBAC（不做 `dataset:create` 这类细粒度权限表）
- 刷新 token / 多端会话管理 / 踢人下线
- 邮箱验证、找回密码、第三方登录（OAuth）
- collection / data 级别的单独授权（授权只到 dataset 层）
- 审计日志

## 2. 总体方案

- **后端**：新增 `users`、`dataset_members` 两张表；新增 `/api/auth`、`/api/users` 路由组与 dataset 成员管理端点；`get_current_user`（JWT）全量替换 `verify_api_key`；涉及 dataset 的端点加角色校验依赖。
- **前端**：新增 `/login`、`/register` 页与 `middleware.ts` 路由守卫；BFF 代理改为从 httpOnly Cookie 读 JWT 转发；新增用户管理页（superuser）与 dataset 成员管理 UI；按 `myRole` 做权限化 UI。
- **worker**：不受影响（不经过 HTTP 认证）。

## 3. 数据模型

遵循现有约定：**不建外键约束**（关联字段为普通字段 + B-tree 索引）、软删除（`isvalid`）、统一 `create_time / update_time / isvalid`（继承 `TimestampValidMixin`）。

### users（用户）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID PK |  |
| username | str, unique index | 登录名，不可改 |
| email | str, unique index, nullable | 可选 |
| password_hash | str | argon2/bcrypt 哈希 |
| is_superuser | bool, default false | 站点管理员 |
| is_active | bool, default true | false 时禁止登录、已发 token 校验失败 |

### dataset_members（知识库成员）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID PK |  |
| dataset_id | UUID, index | 关联 datasets.id |
| user_id | UUID, index | 关联 users.id |
| role | str | `owner / editor / viewer` |

约束：`unique(dataset_id, user_id)`（有效行内唯一，软删行不参与；可用部分唯一索引 `WHERE isvalid = 1` 实现）。

### 角色权限矩阵

| 能力 | owner | editor | viewer | superuser |
| --- | --- | --- | --- | --- |
| search、查看 collections / data | ✅ | ✅ | ✅ | ✅ |
| pushData、编辑/删除 data、collections 增改删 | ✅ | ✅ | ❌ | ✅ |
| 修改 dataset 设置 | ✅ | ✅ | ❌ | ✅ |
| 删除 dataset、管理成员 | ✅ | ❌ | ❌ | ✅ |
| 用户管理（列表/禁用/设超管） | ❌ | ❌ | ❌ | ✅ |

superuser 绕过知识库成员校验（视为对所有 dataset 拥有 owner 能力），但不自动出现在成员列表中。

### 存量数据与种子用户

- 启动时（lifespan）按环境变量 `ADMIN_USERNAME` / `ADMIN_PASSWORD` 种子化一个 superuser（已存在则跳过）。
- **存量 datasets 的回填不在迁移内做**（compose 启动顺序是 `alembic upgrade head && uvicorn`，迁移跑时 users 表必为空）。同样在 lifespan 种子流程中：seed admin 之后，对所有"没有任何有效 owner 成员行"的 dataset 幂等插入该 admin 的 owner 成员行。迁移 `0002_auth` 只负责建表与索引。

## 4. 后端设计

### 4.1 依赖与配置

- 新增依赖：`PyJWT`、`pwdlib[argon2]`（或 `passlib[bcrypt]`，二选一）。登录接口收 JSON body，不需要 `python-multipart`。
- `core/config.py` 新增：`jwt_secret`（必填，无默认）、`jwt_expire_minutes`（默认 7 天）、`admin_username` / `admin_password`（种子用，默认空表示不种子）。
- 移除：`api_keys` 配置与 `api_key_set` 属性。

### 4.2 认证与授权依赖（api/deps.py）

- `get_current_user(request, db) -> User`：解析 `Authorization: Bearer <jwt>`（HS256），校验签名与过期，按 `sub`（user id）查库并校验 `is_active`，失败一律 401 `{detail}`。
- 移除 `verify_api_key`。

**授权依赖按端点族提供，不做通用 path 参数依赖**——现有端点没有统一的 path `dataset_id`：dataset detail/delete 用 `?id=`、update 用 body `{id}`、search 用 body `{datasetId}`、collection/data 写端点只带 `collectionId`/`dataId`。因此：

- `require_dataset_access(min_role)`：覆盖 dataset id 直接在 query/body 的端点族（detail/update/delete/search/members）。
- `require_collection_access(min_role)`：先按 `collectionId`（query 或 body）查 collection 解析出 dataset_id（不存在→404），再角色判定；collection delete 的 body 为 `{collectionIds}` 列表，需全部解析并校验同属一个 dataset。
- `require_data_access(min_role)`：同理按 data id 经 collection 解析。
- 角色判定共用内部函数 `_check_role(user, dataset_id, min_role, db)`：superuser 放行；否则查 `dataset_members` 有效行，角色等级 `owner > editor > viewer` 不足返 403 `{detail: "permission denied"}`；无成员行同样 403。
- body 类端点在依赖内 `await request.json()` 解析（Starlette 会缓存 body，handler 的 Pydantic 解析不受影响）；依赖先于 body 校验执行，body 形状非法时按 422 处理、不做角色判定。

### 4.3 新增 API

JSON 字段一律 camelCase，错误体统一 `{detail}`。

**auth 路由（`routers/auth.py`，前缀 `/api/auth`）**

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| POST | /register | 无 | body `{username, password, email?}` → 创建普通用户 → `{id}` |
| POST | /login | 无 | body `{username, password}` → `{token, user}`；用户禁用或密码错误返 401 |
| GET | /me | 登录 | 返回当前用户 `{id, username, email, isSuperuser}` |

**用户管理路由（`routers/users.py`，前缀 `/api/users`，superuser only）**

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | / | 用户列表，`offset/pageSize` 分页 |
| PATCH | /{userId} | body `{isActive?, isSuperuser?}`；不允许操作自己（防止自我禁用/降权） |

**dataset 成员端点（挂在 `routers/datasets.py`）**

| 方法 | 路径 | min_role | 说明 |
| --- | --- | --- | --- |
| GET | /{datasetId}/members | viewer | 成员列表（含 username） |
| POST | /{datasetId}/members | owner | body `{username, role}` → 添加成员 |
| PATCH | /{datasetId}/members/{userId} | owner | body `{role}` 改角色 |
| DELETE | /{datasetId}/members/{userId} | owner | 移除成员 |

成员约束：有效 owner 至少保留 1 个——移除/降级最后一个 owner 返 422。

### 4.4 现有路由改造

- 所有 router 的 `dependencies=[Depends(verify_api_key)]` 换成 `Depends(get_current_user)`；`/health` 维持无认证。
- 按 §4.2 的端点族依赖加授权：
  - search：`viewer`；collections / data 的读：`viewer`，写：`editor`
  - dataset update：`editor`；dataset delete 与 members 写：`owner`
- `dataset list`：非 superuser 只返回其成员行关联的 datasets；superuser 返回全部。
- `dataset create`：同一事务内写入 creator 的 owner 成员行。
- `dataset detail` 响应增加 `myRole` 字段（`owner/editor/viewer`，superuser 恒为 `owner`），供前端权限化 UI。

### 4.5 代码结构增量

```
api/routers/  + auth.py, users.py
services/     + users.py（注册/登录/种子/成员管理）
repositories/ + users.py, members.py
core/         + security.py（密码哈希、JWT 编解码）
db/models.py  + User, DatasetMember
alembic/versions/ + 0002_auth.py（down_revision = "0001"）
```

### 4.6 测试

- conftest 增加：`JWT_SECRET` 等测试环境变量注入（参照现有 `TEST_DATABASE_URL` 的处理方式，在 Settings 实例化前注入）；user/token fixture 工厂（`make_user(...)`、`auth_headers(user)`）。
- 现有全部测试改走 JWT（fixture 默认创建一个 superuser 注入 headers，减少对旧用例的侵入）；`tests/test_config.py` 的 `api_key_set` 用例删除。
- 新增用例：注册/登录/禁用用户登录失败、token 过期/伪造 401、成员 CRUD、最后 owner 保护、list 过滤。
- **越权（403）用例必须显式使用非 superuser 用户**（viewer 写、editor 管成员、非成员访问），否则超管绕过逻辑会掩盖授权 bug。

## 5. 前端设计

### 5.1 会话与 BFF 代理

- **登录写 Cookie**：新增 `app/api/auth/login/route.ts`，转发登录请求，成功后 `Set-Cookie: session=<jwt>; HttpOnly; SameSite=Lax; Path=/; Max-Age=<jwt_expire>`（生产环境加 `Secure`）。注册走通用代理，不写 Cookie。
- **登出**：`app/api/auth/logout/route.ts` 清除 Cookie。
- **代理改造**（`app/api/proxy/[...path]/route.ts`）：
  - 删除硬编码 `API_KEY`；从请求 Cookie 读 `session`，作为 `Authorization: Bearer` 转发。
  - 路径泛化为代理 `/api/*`（不再写死 `/api/core/dataset/`），覆盖 auth/me、users、members 等新端点。
  - **补充导出 `PATCH`**（users/members 的更新端点用 PATCH，现有代理只有 GET/POST/PUT/DELETE）。
  - 后端 401 原样透传。
- **401 处理防死循环**：客户端 `fetchJson` 拦截 401 时先调用 logout 路由清除 Cookie，再跳 `/login?from=<current>`（否则过期 Cookie 会在 proxy 守卫与 401 跳转间死循环）。
- **路由守卫**：新建 `web/proxy.ts`（**Next.js 16 已将 `middleware.ts` 文件约定更名为 `proxy.ts`**，导出 `proxy` 函数 + `config.matcher`；动手前读 `web/node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/proxy.md`）——无 `session` Cookie 访问 `/datasets/*`、`/settings/*` 重定向 `/login`；已登录访问 `/login`、`/register` 重定向 `/datasets`。只做 Cookie 存在性检查，真伪由后端判定。

### 5.2 页面与组件

- `/login`、`/register`：Card + Input + Label + Button（现有 shadcn 组件），react-hook-form + zod 校验；新增 shadcn `avatar` 组件。注册成功后跳转 `/login?username=<name>` 预填用户名（注册接口不发 token）。
- 根 layout header 右侧加用户菜单（dropdown-menu）：用户名/头像、superuser 可见"用户管理"入口、退出登录。
- `/settings/users`（superuser）：用户列表 Table、`isActive` Switch、`isSuperuser` Switch。
- dataset settings 页新增"成员"区块：按 username 添加成员（Select 选角色）、改角色、移除（alert-dialog 确认）；仅 owner 可见可操作。
- 权限化 UI：依据 dataset detail 的 `myRole` 隐藏/禁用编辑、删除、成员管理入口（viewer 只读 + 可搜索）。

### 5.3 lib / hooks 增量

- `lib/types.ts`：`User`、`Role`（`"owner" | "editor" | "viewer"`）、`DatasetMember`、`AuthUser`；`Dataset` 增加 `myRole`。
- `lib/api.ts`：`authApi`（login/logout/register/me）、`userApi`（list/update）、`memberApi`（list/add/updateRole/remove）。
- `hooks/`：`use-auth.ts`（`useMe` 全局 query + login/logout/register mutations，logout 后清 query cache）、`use-users.ts`、`use-members.ts`。

### 5.4 环境变量

- `docker-compose.yml`：web 服务移除 `API_KEY`；app 服务增加 `JWT_SECRET`、`ADMIN_USERNAME`、`ADMIN_PASSWORD`。
- `.env.example` 同步更新；`AGENTS.md` 中"认证"约定改写为 JWT + BFF Cookie 方案。

## 6. 实施计划

| 阶段 | 内容 | 依赖 |
| --- | --- | --- |
| 1 | 后端认证基座：users 表 + 0002 迁移 + 种子 admin + auth 路由 + `get_current_user` 全量替换 API Key（此阶段所有登录用户全权限，不加成员校验），后端测试全绿 | — |
| 2 | 后端知识库授权：dataset_members + 角色依赖 + 成员端点 + list 过滤 + `myRole` + 越权测试 | 1（模型/迁移接口先约定） |
| 3 | 前端登录闭环：login/register 页 + 会话路由 + 代理改造 + middleware + 用户菜单 | 1 |
| 4 | 前端管理界面：用户管理页 + dataset 成员管理 + 权限化 UI | 2 + 3 |
| 5 | 收尾：compose/env 更新、全栈冒烟、`AGENTS.md` 更新 | 4 |

阶段 1、2 在迁移与模型接口约定后可并行开发；3 依赖 1 的 `/api/auth/*` 契约；4 依赖 2、3。

## 7. 风险与备注

- **外部集成断裂**：API Key 移除后，脚本/集成需改为登录拿 token（后续如有需要可再加 PAT，本期不做）。动手前全局搜 `API_KEY|api_keys|dev-key` 清查残留（backend tests、docs、compose）。
- **JWT 撤销**：token 有效期内禁用用户靠 `is_active` 查库兜底（每次请求查库，非纯无状态校验）；不做 token 黑名单。
- **种子 admin 密码**：仅首次启动生效，生产部署后应立即通过用户管理修改；`JWT_SECRET` 泄漏等于全员可伪造，必须入密管。
- **最后 owner 保护**在 service 层实现：事务内先对 dataset 行 `SELECT ... FOR UPDATE`（或按 dataset_id 取 advisory lock）再计数有效 owner，消除并发降级的 TOCTOU 窗口。
- **登录/注册无速率限制**：开放注册 + 登录存在爆破面，本期作为已知取舍接受，后续可加限流。
- **username 大小写**：注册与登录统一按小写归一化（`Admin` 与 `admin` 视为同一人）。
- **部分唯一索引**：`(dataset_id, user_id)` 有效行唯一用 PG 部分唯一索引 `WHERE isvalid = 1` 实现，只在 Alembic 迁移中声明（`postgresql_where`），ORM 层不再声明普通 `UniqueConstraint`，避免模型与库不一致。
