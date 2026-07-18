from datetime import UTC, datetime

from sqlalchemy import DateTime, SmallInteger
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampValidMixin:
    create_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    update_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    isvalid: Mapped[int] = mapped_column(SmallInteger, default=1)
