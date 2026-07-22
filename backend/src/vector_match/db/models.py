# ruff: noqa: RUF001
import os
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Boolean, DateTime, Index, SmallInteger, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from vector_match.db.base import Base, TimestampValidMixin, utcnow

EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "1024"))


class Dataset(TimestampValidMixin, Base):
    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, comment="知识库ID")
    name: Mapped[str] = mapped_column(String(128), comment="知识库名称")
    description: Mapped[str] = mapped_column(Text, default="", comment="知识库描述")
    vector_model: Mapped[str] = mapped_column(String(128), comment="向量模型名称")


class User(TimestampValidMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_username", "username", unique=True, postgresql_where=text("isvalid = 1")),
        Index("ix_users_email", "email", unique=True, postgresql_where=text("isvalid = 1")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="用户ID")
    username: Mapped[str] = mapped_column(String(64), comment="用户名（登录账号）")
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="邮箱")
    password_hash: Mapped[str] = mapped_column(String(255), comment="密码哈希")
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否超级管理员")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")


class DatasetMember(TimestampValidMixin, Base):
    __tablename__ = "dataset_members"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, comment="成员ID")
    dataset_id: Mapped[uuid.UUID] = mapped_column(index=True, comment="知识库ID")
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, comment="用户ID")
    role: Mapped[str] = mapped_column(String(16), comment="成员角色：owner/editor/viewer")


class Collection(TimestampValidMixin, Base):
    __tablename__ = "collections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, comment="集合ID")
    dataset_id: Mapped[uuid.UUID] = mapped_column(index=True, comment="所属知识库ID")
    parent_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True, comment="父集合ID（空为根级）")
    name: Mapped[str] = mapped_column(String(256), comment="集合名称")
    type: Mapped[str] = mapped_column(String(16), comment="集合类型：folder目录/virtual虚拟集合")


class DatasetData(TimestampValidMixin, Base):
    __tablename__ = "dataset_data"
    __table_args__ = (
        Index(
            "ix_dataset_data_dataset_key",
            "dataset_id",
            "key_id",
            unique=True,
            postgresql_where=text("isvalid = 1 AND key_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, comment="数据ID")
    dataset_id: Mapped[uuid.UUID] = mapped_column(index=True, comment="所属知识库ID")
    collection_id: Mapped[uuid.UUID] = mapped_column(index=True, comment="所属集合ID")
    key_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True, comment="外部源主键")
    source_updatetime: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="外部源更新时间（仅作同步判定）"
    )
    q: Mapped[str] = mapped_column(Text, comment="主文本/问题")
    a: Mapped[str | None] = mapped_column(Text, nullable=True, comment="补充文本/答案")
    full_text_tokens: Mapped[str] = mapped_column(Text, default="", comment="全文检索分词结果（tsvector）")


class DataIndex(TimestampValidMixin, Base):
    __tablename__ = "data_indexes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, comment="索引ID")
    data_id: Mapped[uuid.UUID] = mapped_column(index=True, comment="关联数据ID")
    type: Mapped[str] = mapped_column(String(16), default="custom", comment="索引类型：default默认/custom自定义")
    text: Mapped[str] = mapped_column(Text, comment="索引文本")
    vector = mapped_column(Vector(EMBEDDING_DIM), nullable=True, comment="向量（维度由EMBEDDING_DIM决定）")


class TrainingTask(TimestampValidMixin, Base):
    __tablename__ = "training_tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, comment="任务ID")
    data_id: Mapped[uuid.UUID] = mapped_column(index=True, comment="关联数据ID")
    status: Mapped[str] = mapped_column(
        String(16), default="pending", index=True, comment="任务状态：pending/processing/done/failed"
    )
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0, comment="已尝试次数")
    next_retry_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, comment="下次重试时间"
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True, comment="最近一次错误信息")
