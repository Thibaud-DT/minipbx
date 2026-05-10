from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.time import utc_now


class InboundRoute(Base):
    __tablename__ = "inbound_routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), default="Route entrante principale")
    did_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    use_business_hours: Mapped[bool] = mapped_column(Boolean, default=False)
    business_days: Mapped[str] = mapped_column(String(80), default="mon,tue,wed,thu,fri")
    business_open_time: Mapped[str] = mapped_column(String(5), default="09:00")
    business_close_time: Mapped[str] = mapped_column(String(5), default="18:00")
    holiday_dates: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    open_destination_type: Mapped[str] = mapped_column(String(40), default="extension")
    open_destination_target: Mapped[str | None] = mapped_column(String(80), nullable=True)
    closed_destination_type: Mapped[str] = mapped_column(String(40), default="hangup")
    closed_destination_target: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
