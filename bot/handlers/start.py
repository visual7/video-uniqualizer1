"""
/start, /help, /status, /queue, /cancel, /stats, /export, /import, /language
"""
from __future__ import annotations

import io
import logging
import os
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)

from bot.config import LOCAL_API_URL
from bot.models.user_settings import UserSettings
from bot.queue_worker.worker import queue, JobStatus
from bot.i18n import t, LANGUAGES
from bot.processors.methods import TOTAL_METHODS

logger = logging.getLogger(__name__)
router = Router()


# ── Reply keyboard (language-aware) ───────────────────────────────────────────

def main_keyboard(lang: str) -> ReplyKeyboardMarkup:
    if lang == "ru":
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="🎨 Пресеты")],
                [KeyboardButton(text="📊 Мой статус"), KeyboardButton(text="❓ Помощь")],
            ],
            resize_keyboard=True,
            input_field_placeholder="Отправьте видеофайл для обработки…",
        )
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⚙️ Settings"), KeyboardButton(text="🎨 Presets")],
            [KeyboardButton(text="📊 My status"), KeyboardButton(text="❓ Help")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Send a video file to process…",
    )


def _lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"{emoji} {name}", callback_data=f"lang_set_{code}")
        for code, (emoji, name) in LANGUAGES.items()
    ]])


# ── /language ─────────────────────────────────────────────────────────────────

@router.message(Command("language"))
async def cmd_language(message: Message):
    await message.answer(
        "🌐 Choose language / Выберите язык:",
        reply_markup=_lang_keyboard(),
    )


@router.callback_query(F.data.startswith("lang_set_"))
async def cb_set_language(cb: CallbackQuery):
    lang = cb.data.split("_")[-1]
    if lang not in LANGUAGES:
        await cb.answer()
        return
    s = UserSettings.load(cb.from_user.id)
    s.language = lang
    s.save()
    await cb.answer(t("lang_set", lang))
    # Resend keyboard in new language
    active = sum(1 for ms in s.methods.values() if ms.enabled)
    await cb.message.answer(
        t("welcome", lang) + "\n\n" + t("welcome_active", lang, active=active, total=TOTAL_METHODS),
        parse_mode="HTML",
        reply_markup=main_keyboard(lang),
    )


# ── /start ─────────────────────────────────────────────────────────────────────

@router.message(Command("start"))
async def cmd_start(message: Message):
    # New users see language selection first
    s = UserSettings.load(message.from_user.id)

    # If language not explicitly set yet, show selector
    if not UserSettings._path(message.from_user.id).exists():
        await message.answer(
            "🌐 Choose language / Выберите язык:",
            reply_markup=_lang_keyboard(),
        )
        return

    lang   = s.language
    active = sum(1 for ms in s.methods.values() if ms.enabled)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🟡 " + ("Set «Medium» preset" if lang == "en" else "Установить пресет «Средняя»"),
            callback_data="pre_apply_medium",
        )],
        [
            InlineKeyboardButton(text="⚙️ " + ("Fine tuning" if lang == "en" else "Тонкая настройка"), callback_data="s_main"),
            InlineKeyboardButton(text="📖 " + ("More info" if lang == "en" else "Подробнее"), callback_data="help_full"),
            InlineKeyboardButton(text="🌐", callback_data="lang_menu"),
        ],
    ])

    await message.answer(
        t("welcome", lang) + "\n\n" + t("welcome_active", lang, active=active, total=TOTAL_METHODS),
        parse_mode="HTML",
        reply_markup=main_keyboard(lang),
    )
    await message.answer(
        t("welcome_sub", lang),
        reply_markup=kb,
    )


@router.callback_query(F.data == "lang_menu")
async def cb_lang_menu(cb: CallbackQuery):
    await cb.message.answer("🌐 Choose language / Выберите язык:", reply_markup=_lang_keyboard())
    await cb.answer()


@router.callback_query(F.data == "help_full")
async def cb_help(cb: CallbackQuery):
    s    = UserSettings.load(cb.from_user.id)
    lang = s.language
    await cb.message.answer(t("help_title", lang) + t("help_body", lang, total=TOTAL_METHODS), parse_mode="HTML")
    await cb.answer()


# ── /help ──────────────────────────────────────────────────────────────────────

@router.message(Command("help"))
@router.message(F.text.in_({"❓ Помощь", "❓ Help"}))
async def cmd_help(message: Message):
    s    = UserSettings.load(message.from_user.id)
    lang = s.language
    await message.answer(t("help_title", lang) + t("help_body", lang, total=TOTAL_METHODS), parse_mode="HTML")


# ── /status ────────────────────────────────────────────────────────────────────

@router.message(Command("status"))
@router.message(F.text.in_({"📊 Мой статус", "📊 My status"}))
async def cmd_status(message: Message):
    s    = UserSettings.load(message.from_user.id)
    lang = s.language
    from bot.processors.methods import ALL_CATEGORIES, CATEGORY_NAMES

    active_total = sum(1 for ms in s.methods.values() if ms.enabled)
    g_str = t("status_uniq_on", lang) if s.global_enabled else t("status_uniq_off", lang)

    from bot.processors.methods import PRESETS, PRESET_DISPLAY
    def _detect(s):
        active_ids = {mid for mid, ms in s.methods.items() if ms.enabled}
        for name, cfg in PRESETS.items():
            if active_ids == {int(k) for k, v in cfg.items() if v.get("enabled")}:
                return name
        return None

    lines = [t("status_title", lang), g_str, t("status_active", lang, active=active_total, total=TOTAL_METHODS)]
    preset = _detect(s)
    if preset:
        em, label, _ = PRESET_DISPLAY[preset]
        lines.append(t("status_preset", lang, emoji=em, label=label))
    lines.append("")

    for cat_id in ALL_CATEGORIES:
        emoji, name = CATEGORY_NAMES[cat_id]
        en, tot = s.category_enabled_count(cat_id)
        bar = "█" * en + "░" * (tot - en)
        lines.append(f"{emoji} {name}: {bar} {en}/{tot}")

    lines.append(t("status_processed", lang, total=s.processed_total))

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("btn_change_settings", lang), callback_data="s_main"),
        InlineKeyboardButton(text=t("btn_change_preset", lang),   callback_data="pre_menu"),
    ]])
    await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=kb)


# ── /queue ─────────────────────────────────────────────────────────────────────

@router.message(Command("queue"))
async def cmd_queue(message: Message):
    s    = UserSettings.load(message.from_user.id)
    lang = s.language
    user_jobs = queue.get_user_jobs(message.from_user.id)
    pending   = queue.total_pending()

    if not user_jobs:
        await message.answer(t("queue_empty", lang, pending=pending))
        return

    lines = [t("queue_title", lang, count=len(user_jobs), pending=pending)]
    buttons = []
    has_pending = False

    for i, job in enumerate(user_jobs, 1):
        if job.status == JobStatus.PROCESSING:
            status_str = t("queue_processing", lang, pct=int(job.progress * 100))
        elif job.status == JobStatus.PENDING:
            status_str = t("queue_pending", lang)
        else:
            status_str = "?"
        copies_str = f" x{job.copies}" if job.copies > 1 else ""
        lines.append(t("queue_job_line", lang, i=i, status=status_str, copies=copies_str, job_id=job.id[:6]))

        if job.status == JobStatus.PENDING:
            has_pending = True
            buttons.append([InlineKeyboardButton(
                text=t("btn_cancel_one", lang, i=i),
                callback_data=f"qcancel_{job.id}",
            )])

    if has_pending and len(user_jobs) > 1:
        buttons.append([InlineKeyboardButton(
            text=t("btn_cancel_all", lang),
            callback_data="qcancel_all",
        )])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
    await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith("qcancel_"))
async def cb_queue_cancel(cb: CallbackQuery):
    s    = UserSettings.load(cb.from_user.id)
    lang = s.language
    data = cb.data

    if data == "qcancel_all":
        count = queue.cancel_all_user_jobs(cb.from_user.id)
        if count:
            await cb.message.edit_text(t("cancel_all_done", lang, count=count))
        else:
            await cb.answer(t("err_cancel_impossible", lang), show_alert=True)
    else:
        job_id = data[len("qcancel_"):]
        cancelled = queue.cancel_job(job_id, cb.from_user.id)
        if cancelled:
            await cb.message.edit_text(t("cancel_one_done", lang, job_id=job_id[:6]))
        else:
            await cb.answer(t("err_cancel_impossible", lang), show_alert=True)


# ── /cancel ────────────────────────────────────────────────────────────────────

@router.message(Command("cancel"))
async def cmd_cancel(message: Message):
    s    = UserSettings.load(message.from_user.id)
    lang = s.language
    count = queue.cancel_all_user_jobs(message.from_user.id)
    if count:
        await message.answer(t("cancel_all_done", lang, count=count))
    else:
        active = queue.user_active_jobs(message.from_user.id)
        if active:
            await message.answer(t("cancel_none", lang) + "\n" + t("cancel_impossible", lang))
        else:
            await message.answer(t("cancel_none", lang))


# ── /stats ─────────────────────────────────────────────────────────────────────

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    s    = UserSettings.load(message.from_user.id)
    lang = s.language
    await message.answer(
        t("stats", lang, total=s.processed_total, today=s.processed_today),
        parse_mode="HTML",
    )


# ── /export ────────────────────────────────────────────────────────────────────

@router.message(Command("export"))
async def cmd_export(message: Message):
    s    = UserSettings.load(message.from_user.id)
    lang = s.language
    from aiogram.types import BufferedInputFile
    buf = BufferedInputFile(s.export_json().encode("utf-8"), filename="uniqueluzer_settings.json")
    await message.answer_document(document=buf, caption=t("export_caption", lang), parse_mode="HTML")


# ── /import ────────────────────────────────────────────────────────────────────

# Users waiting to send a file after /import
_awaiting_import: dict[int, bool] = {}

@router.message(Command("import"))
async def cmd_import(message: Message):
    s    = UserSettings.load(message.from_user.id)
    lang = s.language
    text  = message.text or ""
    parts = text.split(maxsplit=1)
    json_str = parts[1].strip() if len(parts) > 1 else ""
    if not json_str:
        # Enter waiting state — next document from this user will be imported
        _awaiting_import[message.from_user.id] = True
        await message.answer(t("import_hint", lang), parse_mode="HTML")
        return
    ok = s.import_json(json_str)
    active = sum(1 for ms in s.methods.values() if ms.enabled)
    await message.answer(
        t("import_ok", lang, active=active, total=TOTAL_METHODS) if ok else t("import_err", lang),
        parse_mode="HTML",
    )


async def _do_import_file(message: Message, bot) -> None:
    """Shared logic for importing settings from a document."""
    s    = UserSettings.load(message.from_user.id)
    lang = s.language
    doc  = message.document
    try:
        file = await bot.get_file(doc.file_id)
        if LOCAL_API_URL and file.file_path and os.path.isabs(file.file_path):
            with open(file.file_path, "rb") as f:
                json_str = f.read().decode("utf-8")
        else:
            data = await bot.download_file(file.file_path)
            json_str = data.read().decode("utf-8")
    except Exception as e:
        await message.answer(f"❌ Не удалось скачать файл: {str(e)[:100]}", parse_mode="HTML")
        return
    ok = s.import_json(json_str)
    active = sum(1 for ms in s.methods.values() if ms.enabled)
    await message.answer(
        t("import_ok", lang, active=active, total=TOTAL_METHODS) if ok else t("import_err", lang),
        parse_mode="HTML",
    )


# Accept file with caption /import
@router.message(F.document & F.caption.func(lambda c: c and c.startswith("/import")))
async def cmd_import_file_caption(message: Message, bot):
    await _do_import_file(message, bot)


# Accept any document after /import command (waiting state)
@router.message(F.document)
async def cmd_import_file_waiting(message: Message, bot):
    uid = message.from_user.id
    if uid not in _awaiting_import:
        return  # not waiting, skip — let video handler process it
    del _awaiting_import[uid]
    await _do_import_file(message, bot)


# ── Reply keyboard button handlers ────────────────────────────────────────────

@router.message(F.text.in_({"⚙️ Настройки", "⚙️ Settings"}))
async def kb_settings(message: Message):
    from bot.handlers.settings import cmd_settings
    await cmd_settings(message)


@router.message(F.text.in_({"🎨 Пресеты", "🎨 Presets"}))
async def kb_presets(message: Message):
    from bot.handlers.presets import cmd_preset
    await cmd_preset(message)
