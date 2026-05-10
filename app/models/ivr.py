from datetime import datetime
from pathlib import Path

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.time import utc_now


class IvrMenu(Base):
    __tablename__ = "ivr_menus"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    number: Mapped[str] = mapped_column(String(6), unique=True, index=True)
    prompt_mode: Mapped[str] = mapped_column(String(20), default="recording")
    prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_audio_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=8)
    fallback_type: Mapped[str] = mapped_column(String(40), default="hangup")
    fallback_target: Mapped[str | None] = mapped_column(String(80), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    options: Mapped[list["IvrOption"]] = relationship(
        back_populates="menu",
        cascade="all, delete-orphan",
    )

    @property
    def playback_path(self) -> str | None:
        if not self.prompt_audio_path:
            return None
        return str(Path(self.prompt_audio_path).with_suffix(""))


class IvrOption(Base):
    __tablename__ = "ivr_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    menu_id: Mapped[int] = mapped_column(ForeignKey("ivr_menus.id", ondelete="CASCADE"))
    digit: Mapped[str] = mapped_column(String(1))
    destination_type: Mapped[str] = mapped_column(String(40))
    destination_target: Mapped[str] = mapped_column(String(80))

    menu: Mapped[IvrMenu] = relationship(back_populates="options")
