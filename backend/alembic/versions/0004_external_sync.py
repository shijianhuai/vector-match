"""external data source sync columns

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-22
"""

# ruff: noqa: RUF001
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dataset_data",
        sa.Column(
            "key_id",
            sa.String(128),
            nullable=True,
            comment="外部源主键",
        ),
    )
    op.add_column(
        "dataset_data",
        sa.Column(
            "source_updatetime",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="外部源更新时间（仅作同步判定）",
        ),
    )
    op.create_index(
        "ix_dataset_data_key_id",
        "dataset_data",
        ["key_id"],
    )
    op.create_index(
        "ix_dataset_data_dataset_key",
        "dataset_data",
        ["dataset_id", "key_id"],
        unique=True,
        postgresql_where=sa.text("isvalid = 1 AND key_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_dataset_data_dataset_key", "dataset_data")
    op.drop_index("ix_dataset_data_key_id", "dataset_data")
    op.drop_column("dataset_data", "source_updatetime")
    op.drop_column("dataset_data", "key_id")
