from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.time import utc_now


class SipTrunk(Base):
    __tablename__ = "sip_trunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), default="Trunk principal")
    host: Mapped[str] = mapped_column(String(255))
    username: Mapped[str] = mapped_column(String(120))
    password_secret: Mapped[str] = mapped_column(String(255))
    from_user: Mapped[str | None] = mapped_column(String(120), nullable=True)
    from_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    transport: Mapped[str] = mapped_column(String(20), default="udp")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
