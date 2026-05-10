from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.time import utc_now


class RingGroup(Base):
    __tablename__ = "ring_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    number: Mapped[str] = mapped_column(String(6), unique=True, index=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=20)
    fallback_type: Mapped[str] = mapped_column(String(40), default="hangup")
    fallback_target: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    members: Mapped[list["RingGroupMember"]] = relationship(
        back_populates="ring_group",
        cascade="all, delete-orphan",
    )


class RingGroupMember(Base):
    __tablename__ = "ring_group_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ring_group_id: Mapped[int] = mapped_column(ForeignKey("ring_groups.id", ondelete="CASCADE"))
    extension_id: Mapped[int] = mapped_column(ForeignKey("extensions.id", ondelete="CASCADE"))

    ring_group: Mapped[RingGroup] = relationship(back_populates="members")
    extension: Mapped["Extension"] = relationship()
