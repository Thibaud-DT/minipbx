from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import PbxSettings


@dataclass(frozen=True)
class EffectivePbxSettings:
    network_mode: str
    sip_port: int
    rtp_start: int
    rtp_end: int
    external_address: str
    local_net: str


def get_pbx_settings(db: Session, settings: Settings) -> EffectivePbxSettings:
    stored = db.get(PbxSettings, 1)
    if not stored:
        return EffectivePbxSettings(
            network_mode="host",
            sip_port=settings.sip_port,
            rtp_start=settings.rtp_start,
            rtp_end=settings.rtp_end,
            external_address=settings.external_address,
            local_net=settings.local_net,
        )
    return EffectivePbxSettings(
        network_mode=stored.network_mode,
        sip_port=stored.sip_port,
        rtp_start=stored.rtp_start,
        rtp_end=stored.rtp_end,
        external_address=stored.external_address,
        local_net=stored.local_net,
    )


def save_pbx_settings(
    db: Session,
    *,
    network_mode: str,
    sip_port: int,
    rtp_start: int,
    rtp_end: int,
    external_address: str,
    local_net: str,
) -> PbxSettings:
    stored = db.get(PbxSettings, 1) or PbxSettings(id=1)
    stored.network_mode = network_mode
    stored.sip_port = sip_port
    stored.rtp_start = rtp_start
    stored.rtp_end = rtp_end
    stored.external_address = external_address.strip()
    stored.local_net = local_net.strip()
    db.add(stored)
    return stored
