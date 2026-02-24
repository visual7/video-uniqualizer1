"""
Handles incoming video (file or URL) — validation, preview, confirmation, batch processing.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import uuid
from pathlib import Path

import aiohttp
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
)

from bot.config import TEMP_DIR, MAX_FILE_SIZE, SUPPORTED_EXTENSIONS, LOCAL_API_URL
from bot.i18n import t
from bot.models.user_settings import UserSettings
from bot.queue_worker.worker import queue, JobStatus
from bot.utils.validators import validate_file, validate_after_probe
from bot.utils.ffmpeg import probe, extract_info

logger = logging.getLogger(__name__)
router = Router()

URL_REGEX = re.compile(
    r"https?://[^\s]+"
    r"\.(?:mp4|mov|avi|mkv|webm|flv|wmv|mpeg|mpg|3gp)(\?[^\s]*)?",
    re.IGNORECASE,
)

# Copy count options
COPY_OPTIONS = [1, 2, 3, 5, 10, 25, 50, 100]

# Intensity variation options (%)
VARIATION_OPTIONS = [0, 5, 10, 20]  # 0 = no variation

# Quick single methods (button label -> list of method_ids to enable)
QUICK_METHODS = {
    "🪞 Mirror only":   [1],
    "💾 Codec only":    [47, 48, 50, 51],
    "🎨 Color only":    [10, 11, 12, 13, 14, 19],
    "🔊 Audio only":    [39, 40, 41, 44, 46],
}

QUICK_METHODS_RU = {
    "🪞 Только зеркало": [1],
    "💾 Только кодек":   [47, 48, 50, 51],
    "🎨 Только цвет":    [10, 11, 12, 13, 14, 19],
    "🔊 Только аудио":   [39, 40, 41, 44, 46],
}

# ── Helpers ──────────────────────────────────────────────────────────────────

_pending_videos: dict[str, dict] = {}    # vid_id → {path, info, user_id}
_user_latest_vid: dict[int, str] = {}   # user_id → latest vid_id (for "back to card")


async def _download_tg_file(bot: Bot, file_id: str, dest: str) -> None:
    """Download a Telegram file. With local API server — copy from disk."""
    file = await bot.get_file(file_id)
    if LOCAL_API_URL and file.file_path and os.path.isabs(file.file_path):
        # Local Bot API server stores files on disk — just copy
        await asyncio.to_thread(shutil.copy2, file.file_path, dest)
    else:
        await bot.download_file(file.file_path, dest)


def has_pending_video(user_id: int) -> bool:
    """Check if user has any pending video (used by settings handler)."""
    vid_id = _user_latest_vid.get(user_id)
    return vid_id is not None and vid_id in _pending_videos


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.0f} KB"
    return f"{size_bytes / (1024 ** 2):.1f} MB"


def _estimate_time(duration: float, methods_count: int) -> str:
    """Rough estimate: ~1s per 10s of video per method cluster."""
    secs = max(5, int(duration * 0.15 + methods_count * 0.5))
    if secs < 60:
        return f"~{secs}s"
    return f"~{secs // 60}m {secs % 60}s"


def _video_card_text(s: UserSettings, lang: str, info: dict) -> str:
    """Builds the info card shown after receiving a video."""
    active_methods = s.get_active_methods()
    active_count = len(active_methods)

    lines = [t("video_received", lang)]

    if not s.global_enabled:
        lines.append(t("video_uniq_off", lang))
    else:
        est = _estimate_time(info["duration"], active_count)
        lines.append(t("video_methods", lang, active=active_count, est=est))

        # Show active categories
        from bot.processors.methods import ALL_CATEGORIES, CATEGORY_NAMES
        cat_counts: dict[int, int] = {}
        for m, ms in active_methods:
            cat_counts[m.category] = cat_counts.get(m.category, 0) + 1
        if cat_counts:
            lines.append("")
            lines.append(t("video_active_cats", lang))
            for cat_id in ALL_CATEGORIES:
                if cat_id in cat_counts:
                    emoji, _ = CATEGORY_NAMES[cat_id]
                    from bot.i18n import cat_name
                    name = cat_name(cat_id, lang)
                    lines.append(f"  {emoji} {name}: {cat_counts[cat_id]}")

    return "\n".join(lines)


def _video_card_kb(vid_id: str, lang: str, copies: int = 1, variation: int = 0) -> InlineKeyboardMarkup:
    """Builds inline keyboard for the video card."""
    rows = []

    # Run button
    if copies == 1:
        rows.append([InlineKeyboardButton(
            text=t("btn_run", lang),
            callback_data=f"vr_{vid_id}_{copies}_{variation}",
        )])
    else:
        var_str = f" ±{variation}%" if variation > 0 else ""
        rows.append([InlineKeyboardButton(
            text=t("btn_run_batch", lang, copies=copies, var=var_str),
            callback_data=f"vr_{vid_id}_{copies}_{variation}",
        )])

    # Copies selector
    copy_row = []
    for n in COPY_OPTIONS:
        label = f"{'▸' if n == copies else ''}{n}×"
        copy_row.append(InlineKeyboardButton(text=label, callback_data=f"vc_{vid_id}_{n}_{variation}"))
    # Split into two rows if needed
    rows.append(copy_row[:4])
    if len(copy_row) > 4:
        rows.append(copy_row[4:])

    # Variation selector (only when copies > 1)
    if copies > 1:
        var_row = []
        for v in VARIATION_OPTIONS:
            label = f"{'▸' if v == variation else ''}±{v}%" if v > 0 else f"{'▸' if v == variation else ''}0%"
            var_row.append(InlineKeyboardButton(text=label, callback_data=f"vv_{vid_id}_{copies}_{v}"))
        rows.append(var_row)

    # Bottom row
    rows.append([
        InlineKeyboardButton(text=t("btn_methods", lang), callback_data="s_main"),
        InlineKeyboardButton(text=t("btn_preset", lang), callback_data="pre_menu"),
        InlineKeyboardButton(text=t("btn_cancel", lang), callback_data=f"vx_{vid_id}"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


# ════════════════════════════════════════════════════════════════════════════
# Receive video file
# ════════════════════════════════════════════════════════════════════════════

@router.message(F.video)
async def on_video(message: Message, bot: Bot):
    user_id = message.from_user.id
    s = UserSettings.load(user_id)
    lang = s.language

    # Rate limit
    ok, wait = queue.check_rate(user_id)
    if not ok:
        await message.answer(t("video_rate_limit", lang, sec=int(wait)))
        return

    # Already processing?
    if queue.user_has_active_job(user_id):
        await message.answer(t("video_already_processing", lang))
        return

    video = message.video

    # Size check (Telegram reports file_size)
    if video.file_size and video.file_size > MAX_FILE_SIZE:
        mb = MAX_FILE_SIZE // (1024 ** 2)
        await message.answer(t("video_too_big", lang, mb=mb))
        return

    # Download
    status_msg = await message.answer(t("video_analysing", lang))

    try:
        ext = ".mp4"
        local_path = str(TEMP_DIR / f"{uuid.uuid4().hex}{ext}")
        await _download_tg_file(bot, video.file_id, local_path)
    except Exception as e:
        logger.error(f"Download failed for user {user_id}: {e}")
        await status_msg.edit_text(t("err_download", lang, e=str(e)[:200]))
        return

    # Validate file
    err = validate_file(local_path)
    if err:
        await status_msg.edit_text(f"❌ {err}")
        _safe_remove(local_path)
        return

    # Probe
    try:
        probe_data = probe(local_path)
        info = extract_info(probe_data)
    except Exception as e:
        logger.error(f"Probe failed for user {user_id}: {e}")
        await status_msg.edit_text(t("err_analyse", lang, e=str(e)[:200]))
        _safe_remove(local_path)
        return

    # Validate after probe
    err = validate_after_probe(info)
    if err:
        await status_msg.edit_text(f"❌ {err}")
        _safe_remove(local_path)
        return

    # Store pending video with unique vid_id
    vid_id = uuid.uuid4().hex[:8]
    _pending_videos[vid_id] = {"path": local_path, "info": info, "user_id": user_id}
    _user_latest_vid[user_id] = vid_id

    # Show video card
    text = _video_card_text(s, lang, info)
    kb = _video_card_kb(vid_id, lang)
    await status_msg.edit_text(text, parse_mode="HTML", reply_markup=kb)


# ════════════════════════════════════════════════════════════════════════════
# Receive video as document (uncompressed)
# ════════════════════════════════════════════════════════════════════════════

@router.message(F.document, ~F.video)
async def on_document(message: Message, bot: Bot):
    doc = message.document
    if not doc.file_name:
        return
    ext = Path(doc.file_name).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return  # Not a video — ignore silently

    user_id = message.from_user.id
    s = UserSettings.load(user_id)
    lang = s.language

    # Rate limit
    ok, wait = queue.check_rate(user_id)
    if not ok:
        await message.answer(t("video_rate_limit", lang, sec=int(wait)))
        return

    # Already processing?
    if queue.user_has_active_job(user_id):
        await message.answer(t("video_already_processing", lang))
        return

    # Size check
    if doc.file_size and doc.file_size > MAX_FILE_SIZE:
        mb = MAX_FILE_SIZE // (1024 ** 2)
        await message.answer(t("video_too_big", lang, mb=mb))
        return

    # Download
    status_msg = await message.answer(t("video_analysing", lang))

    try:
        local_path = str(TEMP_DIR / f"{uuid.uuid4().hex}{ext}")
        await _download_tg_file(bot, doc.file_id, local_path)
    except Exception as e:
        logger.error(f"Download failed for user {user_id}: {e}")
        await status_msg.edit_text(t("err_download", lang, e=str(e)[:200]))
        return

    # Validate
    err = validate_file(local_path)
    if err:
        await status_msg.edit_text(f"❌ {err}")
        _safe_remove(local_path)
        return

    # Probe
    try:
        probe_data = probe(local_path)
        info = extract_info(probe_data)
    except Exception as e:
        logger.error(f"Probe failed for user {user_id}: {e}")
        await status_msg.edit_text(t("err_analyse", lang, e=str(e)[:200]))
        _safe_remove(local_path)
        return

    err = validate_after_probe(info)
    if err:
        await status_msg.edit_text(f"❌ {err}")
        _safe_remove(local_path)
        return

    vid_id = uuid.uuid4().hex[:8]
    _pending_videos[vid_id] = {"path": local_path, "info": info, "user_id": user_id}
    _user_latest_vid[user_id] = vid_id

    text = _video_card_text(s, lang, info)
    kb = _video_card_kb(vid_id, lang)
    await status_msg.edit_text(text, parse_mode="HTML", reply_markup=kb)


# ════════════════════════════════════════════════════════════════════════════
# Receive video URL
# ════════════════════════════════════════════════════════════════════════════

@router.message(F.text.regexp(URL_REGEX))
async def on_video_url(message: Message, bot: Bot):
    url = URL_REGEX.search(message.text).group(0)
    user_id = message.from_user.id
    s = UserSettings.load(user_id)
    lang = s.language

    ok, wait = queue.check_rate(user_id)
    if not ok:
        await message.answer(t("video_rate_limit", lang, sec=int(wait)))
        return

    if queue.user_has_active_job(user_id):
        await message.answer(t("video_already_processing", lang))
        return

    status_msg = await message.answer(t("video_downloading", lang, size="?"))

    ext = Path(url.split("?")[0]).suffix.lower() or ".mp4"
    if ext not in SUPPORTED_EXTENSIONS:
        ext = ".mp4"
    local_path = str(TEMP_DIR / f"{uuid.uuid4().hex}{ext}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=300)) as resp:
                if resp.status != 200:
                    await status_msg.edit_text(f"❌ HTTP {resp.status}")
                    return
                content_length = int(resp.headers.get("content-length", 0))
                if content_length > MAX_FILE_SIZE:
                    mb = MAX_FILE_SIZE // (1024 ** 2)
                    await status_msg.edit_text(t("video_too_big", lang, mb=mb))
                    return

                with open(local_path, "wb") as f:
                    total = 0
                    async for chunk in resp.content.iter_chunked(1024 * 256):
                        f.write(chunk)
                        total += len(chunk)
                        if total > MAX_FILE_SIZE:
                            break

                if total > MAX_FILE_SIZE:
                    mb = MAX_FILE_SIZE // (1024 ** 2)
                    await status_msg.edit_text(t("video_too_big", lang, mb=mb))
                    _safe_remove(local_path)
                    return

    except Exception as e:
        logger.error(f"URL download failed: {e}")
        await status_msg.edit_text(t("err_download", lang, e=str(e)[:200]))
        _safe_remove(local_path)
        return

    await status_msg.edit_text(t("video_analysing", lang))

    err = validate_file(local_path)
    if err:
        await status_msg.edit_text(f"❌ {err}")
        _safe_remove(local_path)
        return

    try:
        probe_data = probe(local_path)
        info = extract_info(probe_data)
    except Exception as e:
        await status_msg.edit_text(t("err_analyse", lang, e=str(e)[:200]))
        _safe_remove(local_path)
        return

    err = validate_after_probe(info)
    if err:
        await status_msg.edit_text(f"❌ {err}")
        _safe_remove(local_path)
        return

    vid_id = uuid.uuid4().hex[:8]
    _pending_videos[vid_id] = {"path": local_path, "info": info, "user_id": user_id}
    _user_latest_vid[user_id] = vid_id

    text = _video_card_text(s, lang, info)
    kb = _video_card_kb(vid_id, lang)
    await status_msg.edit_text(text, parse_mode="HTML", reply_markup=kb)


# ════════════════════════════════════════════════════════════════════════════
# Callbacks — copies / variation selector
# ════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("vc_"))
async def cb_copies(cb: CallbackQuery):
    # vc_{vid_id}_{copies}_{variation}
    parts = cb.data.split("_")
    vid_id = parts[1]
    copies = int(parts[2])
    variation = int(parts[3])
    user_id = cb.from_user.id
    s = UserSettings.load(user_id)
    lang = s.language

    pending = _pending_videos.get(vid_id)
    if not pending:
        await cb.answer(t("file_expired", lang), show_alert=True)
        return

    text = _video_card_text(s, lang, pending["info"])
    if copies > 1:
        var_str = t("variation_val", lang, v=variation) if variation > 0 else ""
        total_est = _estimate_time(pending["info"]["duration"] * copies, len(s.get_active_methods()))
        text += t("video_batch", lang, copies=copies, var=var_str, total=total_est)

    kb = _video_card_kb(vid_id, lang, copies=copies, variation=variation)
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data.startswith("vv_"))
async def cb_variation(cb: CallbackQuery):
    # vv_{vid_id}_{copies}_{variation}
    parts = cb.data.split("_")
    vid_id = parts[1]
    copies = int(parts[2])
    variation = int(parts[3])
    user_id = cb.from_user.id
    s = UserSettings.load(user_id)
    lang = s.language

    pending = _pending_videos.get(vid_id)
    if not pending:
        await cb.answer(t("file_expired", lang), show_alert=True)
        return

    text = _video_card_text(s, lang, pending["info"])
    if copies > 1:
        var_str = t("variation_val", lang, v=variation) if variation > 0 else ""
        total_est = _estimate_time(pending["info"]["duration"] * copies, len(s.get_active_methods()))
        text += t("video_batch", lang, copies=copies, var=var_str, total=total_est)

    kb = _video_card_kb(vid_id, lang, copies=copies, variation=variation)
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await cb.answer()


# ════════════════════════════════════════════════════════════════════════════
# Callback — Run processing
# ════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("vr_"))
async def cb_run(cb: CallbackQuery, bot: Bot):
    # vr_{vid_id}_{copies}_{variation}
    parts = cb.data.split("_")
    vid_id = parts[1]
    copies = int(parts[2])
    variation = int(parts[3])
    user_id = cb.from_user.id
    s = UserSettings.load(user_id)
    lang = s.language

    pending = _pending_videos.pop(vid_id, None)
    if not pending:
        await cb.answer(t("file_expired", lang), show_alert=True)
        return

    local_path = pending["path"]
    if not os.path.exists(local_path):
        await cb.answer(t("file_expired", lang), show_alert=True)
        return

    # Rate limit
    ok, wait = queue.check_rate(user_id)
    if not ok:
        await cb.answer(t("video_rate_limit", lang, sec=int(wait)), show_alert=True)
        _pending_videos[vid_id] = pending  # restore
        return

    if queue.user_has_active_job(user_id):
        await cb.answer(t("video_already_processing", lang), show_alert=True)
        _pending_videos[vid_id] = pending
        return

    # Show progress message
    progress_msg = await cb.message.edit_text(
        t("enqueued", lang),
        parse_mode="HTML",
    )

    # Enqueue
    job = await queue.enqueue(
        user_id=user_id,
        input_path=local_path,
        settings=s,
        chat_id=cb.message.chat.id,
        message_id=progress_msg.message_id,
        copies=copies,
        variation=variation,
    )

    if copies > 1:
        await cb.answer(t("started_batch", lang, n=copies))
    else:
        await cb.answer(t("started", lang))


# ════════════════════════════════════════════════════════════════════════════
# Callback — Cancel (before processing)
# ════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("vx_"))
async def cb_cancel(cb: CallbackQuery):
    # vx_{vid_id}
    vid_id = cb.data.split("_")[1]
    user_id = cb.from_user.id
    s = UserSettings.load(user_id)
    lang = s.language

    pending = _pending_videos.pop(vid_id, None)
    if pending:
        _safe_remove(pending["path"])

    await cb.message.edit_text(t("cancelled_upload", lang))
    await cb.answer()


# ════════════════════════════════════════════════════════════════════════════
# Callback — Back to video card (from settings)
# ════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "vid_back_card")
async def cb_back_card(cb: CallbackQuery):
    user_id = cb.from_user.id
    s = UserSettings.load(user_id)
    lang = s.language

    vid_id = _user_latest_vid.get(user_id)
    pending = _pending_videos.get(vid_id) if vid_id else None
    if not pending:
        await cb.answer(t("file_expired", lang), show_alert=True)
        return

    text = _video_card_text(s, lang, pending["info"])
    kb = _video_card_kb(vid_id, lang)
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await cb.answer()


# ── Utility ──────────────────────────────────────────────────────────────────

def _safe_remove(path: str | None) -> None:
    if path:
        try:
            os.remove(path)
        except OSError:
            pass
