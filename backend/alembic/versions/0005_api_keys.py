"""api keys

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-23
"""

# ruff: noqa: RUF001
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("isvalid", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("creator_id", sa.BigInteger(), nullable=True),
        sa.Column("updater_id", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])
    op.create_index(
        "ix_api_keys_key",
        "api_keys",
        ["key"],
        unique=True,
        postgresql_where=sa.text("isvalid = 1"),
    )

    op.execute("COMMENT ON COLUMN api_keys.id IS 'API Key ID'")
    op.execute("COMMENT ON COLUMN api_keys.user_id IS '用户ID'")
    op.execute("COMMENT ON COLUMN api_keys.name IS 'Key 名称'")
    op.execute("COMMENT ON COLUMN api_keys.key IS 'Key 值'")
    op.execute("COMMENT ON COLUMN api_keys.last_used_at IS '最后使用时间'")
    op.execute("COMMENT ON COLUMN api_keys.create_time IS '创建时间'")
    op.execute("COMMENT ON COLUMN api_keys.update_time IS '更新时间'")
    op.execute("COMMENT ON COLUMN api_keys.isvalid IS '有效标志：1有效0删除'")
    op.execute("COMMENT ON COLUMN api_keys.creator_id IS '创建人ID（users.id），系统操作为空'")
    op.execute("COMMENT ON COLUMN api_keys.updater_id IS '最后更新人ID（users.id），系统操作为空'")


def downgrade() -> None:
    op.drop_index("ix_api_keys_key", table_name="api_keys")
    op.drop_index("ix_api_keys_user_id", table_name="api_keys")
    op.drop_table("api_keys")
