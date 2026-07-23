"""user allow api key

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-23
"""

# ruff: noqa: RUF001
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "allow_api_key",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="是否允许使用 API Key 功能",
        ),
    )
    op.execute("COMMENT ON COLUMN users.allow_api_key IS '是否允许使用 API Key 功能'")


def downgrade() -> None:
    op.drop_column("users", "allow_api_key")
