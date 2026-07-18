import os
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from vector_match.db.base import Base, TimestampValidMixin, utcnow

EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "1024"))


class Dataset(TimestampValidMixin, Base):
    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    vector_model: Mapped[str] = mapped_column(Text)


class Collection(TimestampValidMixin, Base):
    __tablename__ = "collections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    name: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text)  # folder | virtual


class DatasetData(TimestampValidMixin, Base):
    __tablename__ = "dataset_data"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(index=True)
    collection_id: Mapped[uuid.UUID] = mapped_column(index=True)
    q: Mapped[str] = mapped_column(Text)
    a: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_text_tokens: Mapped[str] = mapped_column(Text, default="")


class DataIndex(TimestampValidMixin, Base):
    __tablename__ = "data_indexes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    data_id: Mapped[uuid.UUID] = mapped_column(index=True)
    type: Mapped[str] = mapped_column(Text, default="custom")  # default | custom
    text: Mapped[str] = mapped_column(Text)
    vector = mapped_column(Vector(EMBEDDING_DIM), nullable=True)


class TrainingTask(TimestampValidMixin, Base):
    __tablename__ = "training_tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    data_id: Mapped[uuid.UUID] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(Text, default="pending", index=True)
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    next_retry_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
