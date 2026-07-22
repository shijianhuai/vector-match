# ruff: noqa: RUF001
from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, SmallInteger
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampValidMixin:
    create_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, comment="创建时间"
    )
    update_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, comment="更新时间"
    )
    isvalid: Mapped[int] = mapped_column(
        SmallInteger, default=1, comment="有效标志：1有效0删除"
    )
    creator_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="创建人ID（users.id），系统操作为空"
    )
    updater_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="最后更新人ID（users.id），系统操作为空"
    )
