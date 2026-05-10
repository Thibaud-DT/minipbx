from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import ConfigRevision
from app.services.asterisk import render_configs


@dataclass(frozen=True)
class ConfigState:
    key: str
    label: str
    detail: str
    pending: bool
    last_applied_revision: ConfigRevision | None


def get_config_state(db: Session, settings: Settings) -> ConfigState:
    last_applied = db.scalar(
        select(ConfigRevision).where(ConfigRevision.status == "applied").order_by(ConfigRevision.created_at.desc()).limit(1)
    )
    if not last_applied:
        return ConfigState(
            key="pending",
            label="Modification a appliquer",
            detail="Aucune configuration appliquee.",
            pending=True,
            last_applied_revision=None,
        )

    current_configs = render_configs(db, settings)
    revision_dir = Path(last_applied.generated_path)
    for filename, current_content in current_configs.items():
        applied_file = revision_dir / filename
        if not applied_file.exists() or applied_file.read_text(encoding="utf-8") != current_content:
            return ConfigState(
                key="pending",
                label="Modification a appliquer",
                detail=f"Configuration differente de la revision appliquee {last_applied.id}.",
                pending=True,
                last_applied_revision=last_applied,
            )

    return ConfigState(
        key="up_to_date",
        label="Configuration a jour",
        detail=f"Revision appliquee {last_applied.id}.",
        pending=False,
        last_applied_revision=last_applied,
    )
