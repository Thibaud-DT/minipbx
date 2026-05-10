from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path

from app.models import Extension


VOICEMAIL_FOLDERS = {"INBOX": "Nouveaux", "Old": "Archives"}
VOICEMAIL_AUDIO_EXTENSIONS = {".wav", ".gsm", ".sln", ".ulaw", ".alaw"}


@dataclass(frozen=True)
class VoicemailMessage:
    mailbox: str
    mailbox_name: str
    folder: str
    folder_label: str
    stem: str
    audio_filename: str
    audio_path: Path
    caller_id: str
    orig_date: str
    duration: str
    size_bytes: int

    @property
    def download_url(self) -> str:
        return f"/voicemail/{self.mailbox}/{self.folder}/{self.audio_filename}"


def list_voicemail_messages(spool_dir: Path, extensions: list[Extension]) -> list[VoicemailMessage]:
    names = {extension.number: extension.display_name for extension in extensions}
    messages = []
    for mailbox, mailbox_name in names.items():
        mailbox_dir = spool_dir / mailbox
        for folder, folder_label in VOICEMAIL_FOLDERS.items():
            folder_dir = mailbox_dir / folder
            if not folder_dir.is_dir():
                continue
            for audio_path in sorted(folder_dir.iterdir()):
                if audio_path.suffix.lower() not in VOICEMAIL_AUDIO_EXTENSIONS or not audio_path.is_file():
                    continue
                metadata = _read_metadata(audio_path.with_suffix(".txt"))
                messages.append(
                    VoicemailMessage(
                        mailbox=mailbox,
                        mailbox_name=mailbox_name,
                        folder=folder,
                        folder_label=folder_label,
                        stem=audio_path.stem,
                        audio_filename=audio_path.name,
                        audio_path=audio_path,
                        caller_id=metadata.get("callerid", "Inconnu"),
                        orig_date=metadata.get("origdate", ""),
                        duration=metadata.get("duration", ""),
                        size_bytes=audio_path.stat().st_size,
                    )
                )
    return sorted(messages, key=lambda message: (message.orig_date, message.mailbox, message.stem), reverse=True)


def resolve_voicemail_audio(spool_dir: Path, mailbox: str, folder: str, filename: str) -> Path | None:
    if not _safe_segment(mailbox) or folder not in VOICEMAIL_FOLDERS or not _safe_filename(filename):
        return None
    path = spool_dir / mailbox / folder / filename
    if path.suffix.lower() not in VOICEMAIL_AUDIO_EXTENSIONS or not path.is_file():
        return None
    return path


def delete_voicemail_message(spool_dir: Path, mailbox: str, folder: str, filename: str) -> bool:
    audio_path = resolve_voicemail_audio(spool_dir, mailbox, folder, filename)
    if not audio_path:
        return False
    for sibling in audio_path.parent.glob(f"{audio_path.stem}.*"):
        if sibling.is_file():
            sibling.unlink()
    return True


def _read_metadata(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    parser = ConfigParser()
    try:
        parser.read(path)
    except Exception:
        return {}
    if not parser.has_section("message"):
        return {}
    return {key: value for key, value in parser.items("message")}


def _safe_segment(value: str) -> bool:
    return value.isdigit() and 2 <= len(value) <= 20


def _safe_filename(value: str) -> bool:
    path = Path(value)
    return path.name == value and path.stem.startswith("msg") and path.suffix.lower() in VOICEMAIL_AUDIO_EXTENSIONS
