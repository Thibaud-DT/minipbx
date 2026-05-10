import io
import struct
import wave
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

AUDIO_EXTENSIONS = {".wav", ".gsm", ".sln", ".ulaw", ".alaw"}
MAX_PROMPT_BYTES = 10 * 1024 * 1024
PROMPT_WAV_RATE = 8000
PROMPT_WAV_CHANNELS = 1
PROMPT_WAV_SAMPLE_WIDTH = 2


class PromptFileError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


async def save_prompt_file(prompt_file: UploadFile, prompt_dir: Path, prefix: str) -> Path:
    suffix = Path(prompt_file.filename or "").suffix.lower()
    prompt_dir.mkdir(parents=True, exist_ok=True)
    target = prompt_dir / f"{prefix}-{uuid4().hex}{suffix}"
    content = await prompt_file.read(MAX_PROMPT_BYTES + 1)
    if len(content) > MAX_PROMPT_BYTES:
        raise PromptFileError("fichier-audio-trop-volumineux")
    if suffix == ".wav":
        content = normalize_wav_prompt(content)
    target.write_bytes(content)
    return target


def normalize_wav_prompt(content: bytes) -> bytes:
    try:
        with wave.open(io.BytesIO(content), "rb") as source:
            if source.getcomptype() != "NONE":
                raise PromptFileError("fichier-audio-invalide")
            channels = source.getnchannels()
            sample_width = source.getsampwidth()
            frame_rate = source.getframerate()
            frames = source.readframes(source.getnframes())
    except (EOFError, wave.Error):
        raise PromptFileError("fichier-audio-invalide") from None

    if channels < 1 or sample_width not in {1, 2, 3, 4} or frame_rate <= 0:
        raise PromptFileError("fichier-audio-invalide")

    try:
        samples = _pcm_to_mono_samples(frames, channels, sample_width)
        samples = _resample(samples, frame_rate, PROMPT_WAV_RATE)
        frames = _samples_to_pcm16(samples)
    except (ValueError, OverflowError):
        raise PromptFileError("fichier-audio-invalide") from None

    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(PROMPT_WAV_CHANNELS)
        target.setsampwidth(PROMPT_WAV_SAMPLE_WIDTH)
        target.setframerate(PROMPT_WAV_RATE)
        target.writeframes(frames)
    return output.getvalue()


def _pcm_to_mono_samples(frames: bytes, channels: int, sample_width: int) -> list[int]:
    frame_size = channels * sample_width
    if len(frames) % frame_size:
        raise ValueError("invalid frame size")

    samples: list[int] = []
    for offset in range(0, len(frames), frame_size):
        values = []
        for channel in range(channels):
            start = offset + channel * sample_width
            values.append(_decode_sample(frames[start : start + sample_width], sample_width))
        samples.append(round(sum(values) / len(values)))
    return samples


def _decode_sample(raw: bytes, sample_width: int) -> int:
    if sample_width == 1:
        return (raw[0] - 128) << 8
    if sample_width == 2:
        return int.from_bytes(raw, "little", signed=True)
    if sample_width == 3:
        extended = raw + (b"\xff" if raw[2] & 0x80 else b"\x00")
        return int.from_bytes(extended, "little", signed=True) >> 8
    if sample_width == 4:
        return int.from_bytes(raw, "little", signed=True) >> 16
    raise ValueError("unsupported sample width")


def _resample(samples: list[int], source_rate: int, target_rate: int) -> list[int]:
    if source_rate == target_rate or not samples:
        return samples

    target_length = max(1, round(len(samples) * target_rate / source_rate))
    if target_length == 1:
        return [samples[0]]

    ratio = (len(samples) - 1) / (target_length - 1)
    result = []
    for index in range(target_length):
        source_position = index * ratio
        left = int(source_position)
        right = min(left + 1, len(samples) - 1)
        fraction = source_position - left
        result.append(round(samples[left] * (1 - fraction) + samples[right] * fraction))
    return result


def _samples_to_pcm16(samples: list[int]) -> bytes:
    clipped = [max(-32768, min(32767, sample)) for sample in samples]
    return struct.pack(f"<{len(clipped)}h", *clipped)
