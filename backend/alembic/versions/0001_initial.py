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
    op.execute("CREATE INDEX ix_dataset_data_fts ON dataset_data USING gin (to_tsvector('simple', full_text_tokens))")

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
    op.execute("CREATE INDEX ix_data_indexes_vector_hnsw ON data_indexes USING hnsw (vector vector_cosine_ops)")

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
