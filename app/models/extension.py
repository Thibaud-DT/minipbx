from datetime import datetime
from pathlib import Path

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.time import utc_now


class Extension(Base):
    __tablename__ = "extensions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[str] = mapped_column(String(6), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    sip_username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    sip_secret: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    voicemail_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    voicemail_pin: Mapped[str] = mapped_column(String(12), default="0000")
    voicemail_greeting_mode: Mapped[str] = mapped_column(String(20), default="default")
    voicemail_greeting_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    voicemail_greeting_audio_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    outbound_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    inbound_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    @property
    def voicemail_greeting_playback_path(self) -> str | None:
        if not self.voicemail_greeting_audio_path:
            return None
        return str(Path(self.voicemail_greeting_audio_path).with_suffix(""))
