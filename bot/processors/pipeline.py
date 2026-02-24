"""
Main video processing pipeline.

Flow:
  1. Probe input
  2. Determine active methods (from user settings + seed-based frequency roll)
  3. Build FFmpeg command (video filters + audio filters + encoding opts)
  4. Run FFmpeg
  5. (Optional) run OpenCV methods on the FFmpeg output
  6. If OpenCV was used, merge audio back in
  7. Return output path + report
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import random
import shutil
import time
import uuid
from pathlib import Path
from typing import Callable, Optional

from bot.config import TEMP_DIR, USE_GPU
from bot.utils.ffmpeg import probe, extract_info, run_ffmpeg, FFMPEG_PATH
from bot.utils.validators import validate_file, validate_after_probe
from bot.processors.ffmpeg_builder import BUILDERS, OPENCV_METHODS
from bot.processors.opencv_processor import OPENCV_BUILDERS
from bot.models.user_settings import UserSettings


# ── Hash helper ────────────────────────────────────────────────────────────────

def file_hash(path: str) -> tuple[str, str]:
    """Returns (md5, sha256) hex digests."""
    md5  = hashlib.md5()
    sha  = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            md5.update(chunk)
            sha.update(chunk)
    return md5.hexdigest(), sha.hexdigest()


import re as _re

def _merge_eq_filters(vf_parts: list[str]) -> list[str]:
    """Merge multiple eq= fragments into a single combined eq filter.
    e.g. ['eq=brightness=0.05', 'hue=h=1', 'eq=contrast=1.03']
    →    ['eq=brightness=0.05:contrast=1.03', 'hue=h=1']
    """
    eq_params: dict[str, str] = {}
    merged: list[str] = []

    for part in vf_parts:
        # A part might contain commas (multi-filter chains), process each token
        tokens = part.split(",")
        non_eq_tokens: list[str] = []
        for token in tokens:
            stripped = token.strip()
            if stripped.startswith("eq="):
                # Parse eq params: eq=brightness=0.05:saturation=1.1
                for kv in stripped[3:].split(":"):
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        eq_params[k] = v
            else:
                non_eq_tokens.append(token)
        if non_eq_tokens:
            merged.append(",".join(non_eq_tokens))

    if eq_params:
        eq_str = "eq=" + ":".join(f"{k}={v}" for k, v in eq_params.items())
        merged.insert(0, eq_str)

    return merged


# ── Pipeline ───────────────────────────────────────────────────────────────────

class ProcessingError(Exception):
    pass


async def _pcb(cb, pct: float, msg: str = "") -> None:
    """Call progress callback — supports both sync and async callbacks."""
    if cb is None:
        return
    result = cb(pct, msg)
    if asyncio.iscoroutine(result):
        await result


async def process_video(
    input_path: str,
    user_settings: UserSettings,
    progress_cb: Optional[Callable[[float, str], None]] = None,
    job_seed: Optional[int] = None,
) -> dict:
    """
    Process a video file according to user settings.

    Returns a dict:
        output_path   : str   – path to the processed file
        applied        : list  – list of method names applied
        seed           : int   – seed used
        input_hash_md5  : str
        input_hash_sha  : str
        output_hash_md5 : str
        output_hash_sha : str
        duration_sec    : float – processing time
    """
    start_time = time.time()

    # ── 1. Validate ───────────────────────────────────────────────────────────
    err = validate_file(input_path)
    if err:
        raise ProcessingError(err)

    await _pcb(progress_cb, 0.02, "Анализирую видео…")

    probe_data = probe(input_path)
    info = extract_info(probe_data)
    info["use_gpu"] = USE_GPU

    err = validate_after_probe(info)
    if err:
        raise ProcessingError(err)

    # ── 2. Seed & active methods ──────────────────────────────────────────────
    if job_seed is None:
        job_seed = random.randint(0, 2**32 - 1)

    # Override user setting seed per-job
    rng = random.Random(job_seed)

    active = user_settings.get_active_methods()
    # Shuffle order for randomness
    rng.shuffle(active)

    if not active:
        # No methods active — still re-encode to change hash
        active = []

    applied_names: list[str] = []

    # ── 3. Split methods by type ──────────────────────────────────────────────
    ffmpeg_methods = [(m, ms) for m, ms in active if m.id not in OPENCV_METHODS]
    opencv_methods = [(m, ms) for m, ms in active if m.id in OPENCV_METHODS]

    # ── 4. Build FFmpeg filter chain ──────────────────────────────────────────
    all_vf: list[str] = []
    all_af: list[str] = []
    out_opts: dict    = {}

    # Collect special opts that need merging
    ss_opt   = None
    t_opt    = None

    for method, ms in ffmpeg_methods:
        builder = BUILDERS.get(method.id)
        if builder is None:
            continue
        try:
            vf, af, opts = builder(ms.intensity, job_seed, info)
        except Exception as e:
            # Skip broken method, don't crash
            continue

        # Accumulate
        all_vf.extend(vf)
        all_af.extend(af)

        # Merge output options (later ones override earlier)
        for k, v in opts.items():
            if k == "ss":
                ss_opt = v
            elif k == "t":
                t_opt = v
            else:
                out_opts[k] = v

        applied_names.append(method.name)

    # ── 4b. Merge eq filters ─────────────────────────────────────────────────
    # Multiple eq= filters (brightness, contrast, saturation, gamma) each
    # reset other params to defaults. Merge into one combined eq filter.
    all_vf = _merge_eq_filters(all_vf)

    # ── 4c. Resolve option conflicts ──────────────────────────────────────────
    # CRF + bitrate conflict: when both are set, FFmpeg ignores CRF and uses
    # the bitrate (which can be 500kbps if original bitrate was unknown).
    # Always prefer CRF — it provides predictable, quality-preserving encoding.
    if "crf" in out_opts and "b:v" in out_opts:
        del out_opts["b:v"]

    # ── 5. Assemble FFmpeg command ────────────────────────────────────────────
    job_id  = uuid.uuid4().hex[:12]
    ext     = out_opts.pop("_container", "mp4")

    ffmpeg_out = str(TEMP_DIR / f"{job_id}_ffmpeg.{ext}")

    cmd = [FFMPEG_PATH, "-y"]

    if ss_opt:
        cmd += ["-ss", ss_opt]

    cmd += ["-i", input_path]

    if t_opt:
        cmd += ["-t", t_opt]

    # Video filters
    vf_str = ",".join(filter(None, all_vf))
    if vf_str:
        cmd += ["-vf", vf_str]

    # Audio filters
    if all_af and info.get("has_audio"):
        af_str = ",".join(filter(None, all_af))
        cmd += ["-af", af_str]
    elif not info.get("has_audio"):
        cmd += ["-an"]

    # Output encoding options
    use_gpu = info.get("use_gpu", False)
    if "c:v" not in out_opts:
        out_opts["c:v"] = "h264_nvenc" if use_gpu else "libx264"
    is_nvenc = "nvenc" in out_opts.get("c:v", "")
    if is_nvenc:
        # NVENC uses -qp instead of -crf, and ignores -preset names
        if "crf" not in out_opts and "b:v" not in out_opts and "qp" not in out_opts:
            out_opts["qp"] = "23"
        if "preset" not in out_opts:
            out_opts["preset"] = "p4"  # NVENC fast preset
        # Remove crf if set by a method — NVENC doesn't support it
        out_opts.pop("crf", None)
    else:
        if "crf" not in out_opts and "b:v" not in out_opts:
            out_opts["crf"] = "23"
        if "preset" not in out_opts:
            out_opts["preset"] = "veryfast"
    if "c:a" not in out_opts and info.get("has_audio"):
        out_opts["c:a"] = "aac"
    if "b:a" not in out_opts and info.get("has_audio"):
        out_opts["b:a"] = "128k"
    if "pix_fmt" not in out_opts:
        out_opts["pix_fmt"] = "yuv420p"

    # Metadata opts (multi-key style)
    metadata_opts = []
    for k in list(out_opts.keys()):
        if k.startswith("metadata:"):
            v = out_opts.pop(k)
            metadata_opts.append(("-metadata", v))

    for k, v in out_opts.items():
        cmd += [f"-{k}", v]

    for flag, val in metadata_opts:
        cmd += [flag, val]

    cmd += [ffmpeg_out]

    await _pcb(progress_cb, 0.05, f"Применяю {len(applied_names)} методов…")

    async def ffmpeg_progress(pct: float):
        await _pcb(progress_cb, 0.05 + pct * 0.75, f"Обработка FFmpeg… {int(pct*100)}%")

    try:
        await run_ffmpeg(cmd, progress_cb=ffmpeg_progress, duration=info["duration"])
    except Exception as e:
        raise ProcessingError(f"Ошибка FFmpeg: {e}")

    # Validate FFmpeg output is not empty
    if not os.path.exists(ffmpeg_out) or os.path.getsize(ffmpeg_out) < 1024:
        out_size = os.path.getsize(ffmpeg_out) if os.path.exists(ffmpeg_out) else 0
        _safe_remove(ffmpeg_out)
        raise ProcessingError(f"FFmpeg создал пустой файл ({out_size} байт). Попробуйте другой пресет.")

    current_path = ffmpeg_out

    # ── 6. OpenCV pass ────────────────────────────────────────────────────────
    for method, ms in opencv_methods:
        builder = OPENCV_BUILDERS.get(method.id)
        if builder is None:
            continue

        await _pcb(progress_cb, 0.82, f"OpenCV: {method.name}…")

        cv_out = str(TEMP_DIR / f"{job_id}_cv_{method.id}.mp4")

        try:
            # OpenCV works on video-only, so strip audio first
            video_only = str(TEMP_DIR / f"{job_id}_noaudio.mp4")
            strip_cmd  = [
                FFMPEG_PATH, "-y", "-i", current_path,
                "-an", "-c:v", "libx264", "-crf", "23", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                video_only,
            ]
            await run_ffmpeg(strip_cmd, duration=info["duration"])

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: builder(video_only, cv_out, ms.intensity, job_seed),
            )

            # Re-mux audio from previous step back in
            if info.get("has_audio"):
                muxed = str(TEMP_DIR / f"{job_id}_mux_{method.id}.mp4")
                mux_cmd = [
                    FFMPEG_PATH, "-y",
                    "-i", cv_out,
                    "-i", current_path,
                    "-c:v", "copy",
                    "-c:a", "copy",
                    "-map", "0:v:0",
                    "-map", "1:a:0",
                    "-shortest",
                    muxed,
                ]
                await run_ffmpeg(mux_cmd, duration=info["duration"])
                _safe_remove(current_path)
                _safe_remove(video_only)
                _safe_remove(cv_out)
                current_path = muxed
            else:
                _safe_remove(current_path)
                _safe_remove(video_only)
                current_path = cv_out

        except Exception as e:
            # Skip broken OpenCV method gracefully
            _safe_remove(cv_out)
            continue

        applied_names.append(method.name)

    # ── 7. Compute hashes & return ────────────────────────────────────────────
    await _pcb(progress_cb, 0.95, "Считаю хеши…")

    in_md5,  in_sha  = file_hash(input_path)
    out_md5, out_sha = file_hash(current_path)

    await _pcb(progress_cb, 1.0, "Готово!")

    return {
        "output_path":    current_path,
        "applied":        applied_names,
        "seed":           job_seed,
        "input_hash_md5": in_md5,
        "input_hash_sha": in_sha,
        "output_hash_md5": out_md5,
        "output_hash_sha": out_sha,
        "duration_sec":   round(time.time() - start_time, 1),
        "input_size":     os.path.getsize(input_path),
        "output_size":    os.path.getsize(current_path),
    }


def _safe_remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def build_report(result: dict) -> str:
    """Builds a human-readable result report."""
    from bot.processors.methods import ALL_METHODS, CATEGORY_NAMES

    applied = result["applied"]
    n       = len(applied)
    seed    = result["seed"]
    dur     = result["duration_sec"]
    in_sz   = result["input_size"]  / (1024 ** 2)
    out_sz  = result["output_size"] / (1024 ** 2)
    in_md5  = result["input_hash_md5"]
    out_md5 = result["output_hash_md5"]
    hashes_differ = in_md5 != out_md5

    # Group applied methods by category
    method_by_cat: dict[int, list[str]] = {}
    name_to_cat   = {m.name: m.category for m in ALL_METHODS}
    for name in applied:
        cat = name_to_cat.get(name, 0)
        method_by_cat.setdefault(cat, []).append(name)

    # Build category summary
    cat_lines = []
    for cat_id in sorted(method_by_cat):
        emoji, cat_name = CATEGORY_NAMES.get(cat_id, ("•", "Прочее"))
        names = method_by_cat[cat_id]
        cat_lines.append(f"  {emoji} {cat_name}: {len(names)}")

    cat_block = "\n".join(cat_lines) if cat_lines else "  нет"

    # Duration formatting
    dur_str = f"{dur:.1f} сек" if dur < 60 else f"{dur/60:.1f} мин"

    # Size change
    size_diff = out_sz - in_sz
    size_arrow = f"↑{abs(size_diff):.1f}" if size_diff > 0.1 else (
                 f"↓{abs(size_diff):.1f}" if size_diff < -0.1 else "≈")

    # Hash verification
    hash_line = (
        "✅ Файл уникален — хеш отличается от оригинала"
        if hashes_differ else
        "⚠️ Хеш совпадает с оригиналом"
    )

    return (
        f"✅ <b>Готово! Видео уникализировано</b>\n\n"
        f"{hash_line}\n\n"
        f"<b>Применено методов: {n}</b>\n"
        f"{cat_block}\n\n"
        f"📦 Размер: {in_sz:.1f} МБ → {out_sz:.1f} МБ ({size_arrow} МБ)\n"
        f"⏱ Время: {dur_str}\n"
        f"🔑 Seed: <code>{seed}</code>\n\n"
        f"<b>Хеш-суммы:</b>\n"
        f"<code>Было:  {in_md5[:16]}…</code>\n"
        f"<code>Стало: {out_md5[:16]}…</code>"
    )
