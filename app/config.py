from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="MINIPBX_", extra="ignore")

    web_host: str = "0.0.0.0"
    web_port: int = 8080
    secret_key: str = "change-me"
    session_https_only: bool = False
    session_max_age_seconds: int = 8 * 60 * 60
    csrf_enabled: bool = True
    migrations_enabled: bool = True
    timezone: str = "Europe/Paris"
    country: str = "FR"

    data_dir: Path = Path("/var/lib/minipbx")
    database_url: str | None = None
    generated_config_dir: Path = Path("/var/lib/minipbx/generated")
    prompt_dir: Path = Path("/var/lib/minipbx/prompts")
    asterisk_config_dir: Path = Path("/etc/asterisk")
    backup_dir: Path = Path("/var/lib/minipbx/backups")
    import_dir: Path = Path("/var/lib/minipbx/imports")
    cdr_csv_path: Path = Path("/var/log/asterisk/cdr-csv/Master.csv")
    voicemail_spool_dir: Path = Path("/var/spool/asterisk/voicemail/default")

    asterisk_reload_command: str = "asterisk -C /etc/asterisk/asterisk.conf -rx 'core reload'"
    asterisk_status_command: str = "asterisk -C /etc/asterisk/asterisk.conf -rx 'core show uptime'"
    asterisk_apply_enabled: bool = True
    admin_username: str = "admin"
    ami_enabled: bool = True
    ami_bind_address: str = "127.0.0.1"
    ami_port: int = 5038
    ami_username: str = "minipbx"
    ami_password: str = "change-me"
    tts_backend: str = "none"

    sip_port: int = Field(default=5060, validation_alias="ASTERISK_SIP_PORT")
    rtp_start: int = Field(default=10000, validation_alias="ASTERISK_RTP_START")
    rtp_end: int = Field(default=10100, validation_alias="ASTERISK_RTP_END")
    external_address: str = Field(default="", validation_alias="ASTERISK_EXTERNAL_ADDRESS")
    local_net: str = Field(default="192.168.1.0/24", validation_alias="ASTERISK_LOCAL_NET")

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{self.data_dir / 'minipbx.db'}"

    def validate_runtime(self) -> None:
        insecure_values = {"", "change-me", "change-me-generate-with-install-sh"}
        if self.secret_key in insecure_values:
            raise RuntimeError("MINIPBX_SECRET_KEY doit etre defini avec une valeur aleatoire avant le demarrage.")
        if self.asterisk_apply_enabled and self.ami_enabled and self.ami_password in insecure_values:
            raise RuntimeError("MINIPBX_AMI_PASSWORD doit etre defini avec une valeur aleatoire avant le demarrage.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
