from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.time import utc_now


class PbxSettings(Base):
    __tablename__ = "pbx_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    network_mode: Mapped[str] = mapped_column(String(20), default="host")
    sip_port: Mapped[int] = mapped_column(Integer, default=5060)
    rtp_start: Mapped[int] = mapped_column(Integer, default=10000)
    rtp_end: Mapped[int] = mapped_column(Integer, default=10100)
    external_address: Mapped[str] = mapped_column(String(120), default="")
    local_net: Mapped[str] = mapped_column(String(80), default="192.168.1.0/24")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
