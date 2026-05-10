from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.time import utc_now


class OutboundRule(Base):
    __tablename__ = "outbound_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), default="Regles sortantes principales")
    prefix: Mapped[str | None] = mapped_column(String(8), nullable=True)
    allow_national: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_mobile: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_international: Mapped[bool] = mapped_column(Boolean, default=False)
    emergency_numbers: Mapped[str] = mapped_column(String(255), default="15,17,18,112")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
