"""user roles and approval

Revision ID: c9639efcc9da
Revises: 0006
Create Date: 2026-07-23 17:41:36.962808

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9639efcc9da'
down_revision: Union[str, Sequence[str], None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ROLE_DEFAULT = 'user'
APPROVED_DEFAULT = False


def upgrade() -> None:
    # 新增角色与审批字段
    op.add_column('users', sa.Column('role', sa.String(length=16), nullable=True))
    op.add_column('users', sa.Column('is_approved', sa.Boolean(), nullable=True))

    # 回刷：原超级管理员保留为 superadmin 且已审批；其余用户保持可登录
    op.execute("UPDATE users SET role = 'superadmin', is_approved = true WHERE is_superuser = true")
    op.execute("UPDATE users SET role = 'user', is_approved = true WHERE role IS NULL")

    # 设置非空与默认值
    op.alter_column('users', 'role', nullable=False, server_default=ROLE_DEFAULT)
    op.alter_column('users', 'is_approved', nullable=False, server_default=str(APPROVED_DEFAULT).lower())

    # 移除旧字段
    op.drop_column('users', 'is_superuser')
    op.drop_column('users', 'allow_api_key')


def downgrade() -> None:
    # 恢复旧字段
    op.add_column('users', sa.Column('is_superuser', sa.Boolean(), nullable=True))
    op.add_column('users', sa.Column('allow_api_key', sa.Boolean(), nullable=True))

    # 近似回刷：superadmin 恢复为 is_superuser=true
    op.execute("UPDATE users SET is_superuser = true WHERE role = 'superadmin'")
    op.execute("UPDATE users SET is_superuser = false WHERE role != 'superadmin'")
    op.execute("UPDATE users SET allow_api_key = false")

    op.alter_column('users', 'is_superuser', nullable=False, server_default='false')
    op.alter_column('users', 'allow_api_key', nullable=False, server_default='false')

    op.drop_column('users', 'role')
    op.drop_column('users', 'is_approved')
