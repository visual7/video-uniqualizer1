"""FFmpeg / FFprobe helpers."""
from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Optional

from bot.config import FFMPEG_PATH, FFPROBE_PATH


# ── Probe ──────────────────────────────────────────────────────────────────────

def probe(file_path: str) -> dict:
    """
    Returns a dict with video/audio stream information.
    Raises RuntimeError on failure.
    """
    cmd = [
        FFPROBE_PATH, "-v", "quiet", "-print_format", "json",
        "-show_streams", "-show_format", file_path,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr}")
        return json.loads(result.stdout)
    except FileNotFoundError:
        raise RuntimeError(f"ffprobe not found at '{FFPROBE_PATH}'")
    except subprocess.TimeoutExpired:
        raise RuntimeError("ffprobe timed out")


def extract_info(probe_data: dict) -> dict:
    """Parses ffprobe output into a flat info dict used by builders."""
    streams  = probe_data.get("streams", [])
    fmt      = probe_data.get("format", {})

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    width  = int(video_stream.get("width",  1920) if video_stream else 1920)
    height = int(video_stream.get("height", 1080) if video_stream else 1080)

    # Parse FPS fraction like "30000/1001"
    fps = 30.0
    if video_stream:
        fps_str = video_stream.get("r_frame_rate", "30/1")
        try:
            num, den = fps_str.split("/")
            fps = float(num) / float(den)
        except Exception:
            pass

    duration = 0.0
    try:
        duration = float(fmt.get("duration", 0))
    except Exception:
        pass

    bitrate = 0
    try:
        bitrate = int(int(fmt.get("bit_rate", 0)) / 1000)
    except Exception:
        pass

    audio_sr = 44100
    if audio_stream:
        try:
            audio_sr = int(audio_stream.get("sample_rate", 44100))
        except Exception:
            pass

    return {
        "width":              width,
        "height":             height,
        "fps":                fps,
        "duration":           duration,
        "video_bitrate":      bitrate,
        "has_audio":          audio_stream is not None,
        "audio_sample_rate":  audio_sr,
        "video_codec":        video_stream.get("codec_name", "h264") if video_stream else "h264",
        "audio_codec":        audio_stream.get("codec_name", "aac")  if audio_stream else "",
    }


# ── Run FFmpeg ─────────────────────────────────────────────────────────────────

async def run_ffmpeg(
    cmd: list[str],
    progress_cb=None,
    duration: float = 0,
) -> None:
    """
    Runs an FFmpeg command asynchronously.
    Calls progress_cb(0.0–1.0) based on time=... lines in stderr.
    Raises RuntimeError on non-zero exit.
    """
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )

    stderr_data = []
    time_re = re.compile(r"time=(\d+):(\d+):(\d+)\.(\d+)")

    async for line in process.stderr:
        line_str = line.decode("utf-8", errors="replace").strip()
        stderr_data.append(line_str)
        if progress_cb and duration > 0:
            m = time_re.search(line_str)
            if m:
                h, mi, s, cs = int(m[1]), int(m[2]), int(m[3]), int(m[4])
                elapsed = h * 3600 + mi * 60 + s + cs / 100
                result = progress_cb(min(0.99, elapsed / duration))
                if asyncio.iscoroutine(result):
                    await result

    await process.wait()

    if process.returncode != 0:
        error_tail = "\n".join(stderr_data[-20:])
        raise RuntimeError(f"FFmpeg exited {process.returncode}:\n{error_tail}")

    if progress_cb:
        result = progress_cb(1.0)
        if asyncio.iscoroutine(result):
            await result


# ── Utility ────────────────────────────────────────────────────────────────────

def ffmpeg_available() -> bool:
    try:
        r = subprocess.run(
            [FFMPEG_PATH, "-version"],
            capture_output=True, timeout=5
        )
        return r.returncode == 0
    except Exception:
        return False

def ffprobe_available() -> bool:
    try:
        r = subprocess.run(
            [FFPROBE_PATH, "-version"],
            capture_output=True, timeout=5
        )
        return r.returncode == 0
    except Exception:
        return False
