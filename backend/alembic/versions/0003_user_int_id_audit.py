"""user int id and audit columns

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-22
"""

# ruff: noqa: RUF001
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

_AUDIT_TABLES = [
    "datasets",
    "users",
    "dataset_members",
    "collections",
    "dataset_data",
    "data_indexes",
    "training_tasks",
]

_COLUMN_COMMENTS = [
    ("datasets", "id", "知识库ID"),
    ("datasets", "name", "知识库名称"),
    ("datasets", "description", "知识库描述"),
    ("datasets", "vector_model", "向量模型名称"),
    ("users", "id", "用户ID"),
    ("users", "username", "用户名（登录账号）"),
    ("users", "email", "邮箱"),
    ("users", "password_hash", "密码哈希"),
    ("users", "is_superuser", "是否超级管理员"),
    ("users", "is_active", "是否启用"),
    ("dataset_members", "id", "成员ID"),
    ("dataset_members", "dataset_id", "知识库ID"),
    ("dataset_members", "user_id", "用户ID"),
    ("dataset_members", "role", "成员角色：owner/editor/viewer"),
    ("collections", "id", "集合ID"),
    ("collections", "dataset_id", "所属知识库ID"),
    ("collections", "parent_id", "父集合ID（空为根级）"),
    ("collections", "name", "集合名称"),
    ("collections", "type", "集合类型：folder目录/virtual虚拟集合"),
    ("dataset_data", "id", "数据ID"),
    ("dataset_data", "dataset_id", "所属知识库ID"),
    ("dataset_data", "collection_id", "所属集合ID"),
    ("dataset_data", "q", "主文本/问题"),
    ("dataset_data", "a", "补充文本/答案"),
    ("dataset_data", "full_text_tokens", "全文检索分词结果（tsvector）"),
    ("data_indexes", "id", "索引ID"),
    ("data_indexes", "data_id", "关联数据ID"),
    ("data_indexes", "type", "索引类型：default默认/custom自定义"),
    ("data_indexes", "text", "索引文本"),
    ("data_indexes", "vector", "向量（维度由EMBEDDING_DIM决定）"),
    ("training_tasks", "id", "任务ID"),
    ("training_tasks", "data_id", "关联数据ID"),
    ("training_tasks", "status", "任务状态：pending/processing/done/failed"),
    ("training_tasks", "attempts", "已尝试次数"),
    ("training_tasks", "next_retry_at", "下次重试时间"),
    ("training_tasks", "last_error", "最近一次错误信息"),
]


def _add_comments() -> None:
    for table, column, comment in _COLUMN_COMMENTS:
        op.execute(f"COMMENT ON COLUMN {table}.{column} IS '{comment}'")

    for table in _AUDIT_TABLES:
        op.execute(f"COMMENT ON COLUMN {table}.create_time IS '创建时间'")
        op.execute(f"COMMENT ON COLUMN {table}.update_time IS '更新时间'")
        op.execute(f"COMMENT ON COLUMN {table}.isvalid IS '有效标志：1有效0删除'")
        op.execute(f"COMMENT ON COLUMN {table}.creator_id IS '创建人ID（users.id），系统操作为空'")
        op.execute(f"COMMENT ON COLUMN {table}.updater_id IS '最后更新人ID（users.id），系统操作为空'")


def upgrade() -> None:
    # 1. Audit columns
    for table in _AUDIT_TABLES:
        op.add_column(
            table,
            sa.Column(
                "creator_id",
                sa.BigInteger(),
                nullable=True,
                comment="创建人ID（users.id），系统操作为空",
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "updater_id",
                sa.BigInteger(),
                nullable=True,
                comment="最后更新人ID（users.id），系统操作为空",
            ),
        )

    # 2. Short TEXT -> VARCHAR
    op.alter_column(
        "datasets", "name", existing_type=sa.Text(), type_=sa.VARCHAR(128), nullable=False
    )
    op.alter_column(
        "datasets", "vector_model", existing_type=sa.Text(), type_=sa.VARCHAR(128), nullable=False
    )
    op.alter_column(
        "users", "username", existing_type=sa.Text(), type_=sa.VARCHAR(64), nullable=False
    )
    op.alter_column(
        "users", "email", existing_type=sa.Text(), type_=sa.VARCHAR(255), nullable=True
    )
    op.alter_column(
        "users", "password_hash", existing_type=sa.Text(), type_=sa.VARCHAR(255), nullable=False
    )
    op.alter_column(
        "dataset_members", "role", existing_type=sa.Text(), type_=sa.VARCHAR(16), nullable=False
    )
    op.alter_column(
        "collections", "name", existing_type=sa.Text(), type_=sa.VARCHAR(256), nullable=False
    )
    op.alter_column(
        "collections", "type", existing_type=sa.Text(), type_=sa.VARCHAR(16), nullable=False
    )
    op.alter_column(
        "data_indexes", "type", existing_type=sa.Text(), type_=sa.VARCHAR(16), nullable=False
    )
    op.alter_column(
        "training_tasks",
        "status",
        existing_type=sa.Text(),
        type_=sa.VARCHAR(16),
        nullable=False,
        server_default="pending",
    )

    # 3. users.id uuid -> bigint, keep dataset_members mapping intact
    op.execute("ALTER TABLE users ADD COLUMN id_new bigint GENERATED ALWAYS AS IDENTITY")
    op.execute("ALTER TABLE dataset_members ADD COLUMN user_id_new bigint")
    op.execute(
        "UPDATE dataset_members dm SET user_id_new = u.id_new FROM users u WHERE u.id = dm.user_id"
    )

    # Remove old user_id column and its dependent indexes.
    op.drop_index("ix_dataset_members_user_id", "dataset_members")
    op.drop_index("ix_dataset_members_dataset_id_user_id_valid", "dataset_members")
    op.execute("ALTER TABLE dataset_members DROP COLUMN user_id")
    op.execute("ALTER TABLE dataset_members RENAME COLUMN user_id_new TO user_id")
    op.alter_column(
        "dataset_members", "user_id", existing_type=sa.BigInteger(), nullable=False
    )
    op.create_index("ix_dataset_members_user_id", "dataset_members", ["user_id"])
    op.create_index(
        "ix_dataset_members_dataset_id_user_id_valid",
        "dataset_members",
        ["dataset_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("isvalid = 1"),
    )

    # Swap users primary key to the new bigint column.
    op.execute("ALTER TABLE users DROP CONSTRAINT users_pkey")
    op.execute("ALTER TABLE users DROP COLUMN id")
    op.execute("ALTER TABLE users RENAME COLUMN id_new TO id")
    op.alter_column("users", "id", existing_type=sa.BigInteger(), nullable=False)
    op.create_primary_key("users_pkey", "users", ["id"])

    # 4. Comments on all columns
    _add_comments()


def downgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # Reverse users.id / dataset_members.user_id back to uuid.
    op.drop_index("ix_dataset_members_dataset_id_user_id_valid", "dataset_members")
    op.drop_index("ix_dataset_members_user_id", "dataset_members")

    op.execute("ALTER TABLE users ADD COLUMN id_new uuid NOT NULL DEFAULT gen_random_uuid()")
    op.execute("ALTER TABLE dataset_members ADD COLUMN user_id_new uuid")
    op.execute(
        "UPDATE dataset_members dm SET user_id_new = u.id_new FROM users u WHERE u.id = dm.user_id"
    )
    op.execute("ALTER TABLE dataset_members DROP COLUMN user_id")
    op.execute("ALTER TABLE dataset_members RENAME COLUMN user_id_new TO user_id")
    op.alter_column("dataset_members", "user_id", existing_type=sa.Uuid(), nullable=False)
    op.create_index("ix_dataset_members_user_id", "dataset_members", ["user_id"])
    op.create_index(
        "ix_dataset_members_dataset_id_user_id_valid",
        "dataset_members",
        ["dataset_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("isvalid = 1"),
    )

    op.execute("ALTER TABLE users DROP CONSTRAINT users_pkey")
    op.execute("ALTER TABLE users DROP COLUMN id")
    op.execute("ALTER TABLE users RENAME COLUMN id_new TO id")
    op.alter_column("users", "id", existing_type=sa.Uuid(), nullable=False)
    op.execute("ALTER TABLE users ALTER COLUMN id SET DEFAULT gen_random_uuid()")
    op.create_primary_key("users_pkey", "users", ["id"])

    # Reverse VARCHAR -> TEXT
    op.alter_column(
        "training_tasks",
        "status",
        existing_type=sa.VARCHAR(16),
        type_=sa.Text(),
        nullable=False,
        server_default="pending",
    )
    op.alter_column(
        "data_indexes", "type", existing_type=sa.VARCHAR(16), type_=sa.Text(), nullable=False
    )
    op.alter_column(
        "collections", "type", existing_type=sa.VARCHAR(16), type_=sa.Text(), nullable=False
    )
    op.alter_column(
        "collections", "name", existing_type=sa.VARCHAR(256), type_=sa.Text(), nullable=False
    )
    op.alter_column(
        "dataset_members", "role", existing_type=sa.VARCHAR(16), type_=sa.Text(), nullable=False
    )
    op.alter_column(
        "users", "password_hash", existing_type=sa.VARCHAR(255), type_=sa.Text(), nullable=False
    )
    op.alter_column(
        "users", "email", existing_type=sa.VARCHAR(255), type_=sa.Text(), nullable=True
    )
    op.alter_column(
        "users", "username", existing_type=sa.VARCHAR(64), type_=sa.Text(), nullable=False
    )
    op.alter_column(
        "datasets", "vector_model", existing_type=sa.VARCHAR(128), type_=sa.Text(), nullable=False
    )
    op.alter_column(
        "datasets", "name", existing_type=sa.VARCHAR(128), type_=sa.Text(), nullable=False
    )

    # Drop audit columns
    for table in _AUDIT_TABLES:
        op.drop_column(table, "updater_id")
        op.drop_column(table, "creator_id")
