"""
Input validation: format, size, magic bytes, codec, duration.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from bot.config import (
    MAX_FILE_SIZE, MAX_DURATION, SUPPORTED_EXTENSIONS, SUPPORTED_MIME_PREFIXES
)

# ── Magic bytes for common video formats ──────────────────────────────────────
_MAGIC_SIGNATURES = {
    b"\x00\x00\x00": "mp4/mov/3gp",          # ISO base media (4-byte box)
    b"\x1a\x45\xdf\xa3": "mkv/webm",
    b"FLV": "flv",
    b"RIFF": "avi",
    b"\x30\x26\xb2\x75": "wmv/asf",
    b"\x00\x00\x01\xb3": "mpeg",
    b"\x00\x00\x01\xba": "mpeg",
}

_MAX_MAGIC_READ = 12  # bytes


def check_magic_bytes(path: str) -> bool:
    """Returns True if the file looks like a video based on magic bytes."""
    try:
        with open(path, "rb") as f:
            header = f.read(_MAX_MAGIC_READ)
    except OSError:
        return False

    for magic, _ in _MAGIC_SIGNATURES.items():
        if header[:len(magic)] == magic:
            return True

    # MP4/MOV: ftyp box at offset 4
    if len(header) >= 8 and header[4:8] in (
        b"ftyp", b"moov", b"mdat", b"free", b"skip", b"wide", b"pnot"
    ):
        return True

    return False


def validate_file(path: str) -> Optional[str]:
    """
    Returns None if file is valid, or an error string if not.
    """
    p = Path(path)

    # Existence
    if not p.exists():
        return "Файл не найден."

    # Size
    size = p.stat().st_size
    if size == 0:
        return "Файл пустой."
    if size > MAX_FILE_SIZE:
        mb = MAX_FILE_SIZE // (1024 ** 2)
        return f"Файл слишком большой. Максимум: {mb} МБ."

    # Extension
    ext = p.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return (
            f"Формат {ext!r} не поддерживается.\n"
            f"Поддерживаемые: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    # Magic bytes check
    if not check_magic_bytes(path):
        return "Файл не является корректным видеофайлом (проверка сигнатуры не пройдена)."

    return None


def validate_after_probe(info: dict) -> Optional[str]:
    """
    Validates probed video info (duration, codec, resolution).
    Returns None if OK, or error string.
    """
    duration = info.get("duration", 0)

    if MAX_DURATION > 0 and duration > MAX_DURATION:
        return f"Длительность видео ({duration:.0f}с) превышает лимит ({MAX_DURATION}с)."

    if duration == 0:
        return "Не удалось определить длительность видео."

    width  = info.get("width",  0)
    height = info.get("height", 0)
    if width == 0 or height == 0:
        return "Не удалось определить разрешение видео."

    return None
