"""auth: users table

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-21
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _common_columns() -> list[sa.Column]:
    return [
        sa.Column("create_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("update_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("isvalid", sa.SmallInteger(), nullable=False, server_default="1"),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        *_common_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_users_username",
        "users",
        ["username"],
        unique=True,
        postgresql_where=sa.text("isvalid = 1"),
    )
    op.create_index(
        "ix_users_email",
        "users",
        ["email"],
        unique=True,
        postgresql_where=sa.text("isvalid = 1"),
    )

    op.create_table(
        "dataset_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        *_common_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dataset_members_dataset_id", "dataset_members", ["dataset_id"])
    op.create_index("ix_dataset_members_user_id", "dataset_members", ["user_id"])
    op.create_index(
        "ix_dataset_members_dataset_id_user_id_valid",
        "dataset_members",
        ["dataset_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("isvalid = 1"),
    )


def downgrade() -> None:
    op.drop_index("ix_dataset_members_dataset_id_user_id_valid", table_name="dataset_members")
    op.drop_index("ix_dataset_members_user_id", table_name="dataset_members")
    op.drop_index("ix_dataset_members_dataset_id", table_name="dataset_members")
    op.drop_table("dataset_members")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
