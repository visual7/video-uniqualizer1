"""
Settings inline keyboard — full tree:
  Main menu → Category → Method detail

Callback format: s_<action>_<params>
  s_main              — show main menu
  s_cat_<cat>         — show category
  s_met_<mid>         — show method detail
  s_tg_gl             — toggle global
  s_tg_cat_<cat>      — toggle all in category
  s_tg_<mid>          — toggle method
  s_int_<mid>_up/dn/max/min — intensity ±10
  s_int_<mid>_edit     — type custom intensity (1-100%)
  s_frq_<mid>_up/dn/max — freq +10 / -10 / 100%
"""
from __future__ import annotations

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from bot.i18n import t, cat_name, method_name
from bot.models.user_settings import UserSettings, intensity_bar
from bot.processors.methods import (
    ALL_METHODS, ALL_CATEGORIES, CATEGORY_NAMES, TOTAL_METHODS,
    get_methods_by_category, get_method, PARAM_ONOFF,
    get_real_label,
)

logger = logging.getLogger(__name__)
router = Router()


# ════════════════════════════════════════════════════════════════════════════
# Keyboard builders
# ════════════════════════════════════════════════════════════════════════════

def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


CATEGORY_HINTS = {
    "en": {
        1: "flip, rotate, zoom, crop, parallax",
        2: "brightness, contrast, color, hue",
        3: "sharpen, blur, motion blur",
        4: "grain, noise, chromatic aberration",
        5: "FPS, speed, trim start/end",
        6: "pitch, EQ, reverb, loudness",
        7: "codec, bitrate, metadata, GOP",
        8: "invisible watermark, border, pixels",
        9: "DCT, warp, steganography",
    },
    "ru": {
        1: "зеркало, поворот, зум, кадрирование, параллакс",
        2: "яркость, контраст, цвет, оттенок",
        3: "резкость, размытие, motion blur",
        4: "зернистость, шум, хром. аберрация",
        5: "FPS, скорость, обрезка начала/конца",
        6: "тон, эквалайзер, реверб, громкость",
        7: "кодек, битрейт, метаданные, GOP",
        8: "невидимый знак, рамка, пиксели",
        9: "DCT, деформации, стеганография",
    },
}


def kb_main(s: UserSettings, lang: str, has_pending_video: bool = False) -> InlineKeyboardMarkup:
    rows = []

    # Global toggle
    if s.global_enabled:
        rows.append([_btn(t("btn_uniq_on", lang), "s_tg_gl")])
    else:
        rows.append([_btn(t("btn_uniq_off", lang), "s_tg_gl")])

    # Categories
    for cat_id in ALL_CATEGORIES:
        emoji, _ = CATEGORY_NAMES[cat_id]
        name = cat_name(cat_id, lang)
        en, tot = s.category_enabled_count(cat_id)
        check = "✅" if en == tot else ("🔸" if en > 0 else "⬜")
        rows.append([_btn(
            f"{check} {emoji} {name}  [{en}/{tot}]",
            f"s_cat_{cat_id}",
        )])

    # Bottom row — with language switcher
    bottom = [
        _btn(t("btn_presets", lang), "pre_menu"),
        _btn(t("btn_export", lang),  "s_exp"),
        _btn("🌐",                   "lang_menu"),
        _btn(t("btn_close", lang),   "s_close"),
    ]
    rows.append(bottom)

    # Back to video card button (when user has a pending video)
    if has_pending_video:
        rows.append([_btn(t("btn_back_card", lang), "vid_back_card")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_category(cat_id: int, s: UserSettings, lang: str) -> InlineKeyboardMarkup:
    methods = get_methods_by_category(cat_id)
    emoji, _ = CATEGORY_NAMES[cat_id]
    name = cat_name(cat_id, lang)
    rows = []

    # Header
    en, tot = s.category_enabled_count(cat_id)
    all_on = en == tot
    if all_on:
        toggle_btn_text = t("btn_all_off", lang, en=en, tot=tot)
    else:
        toggle_btn_text = t("btn_all_on", lang, en=en, tot=tot)
    rows.append([
        _btn(t("btn_back", lang),  "s_main"),
        _btn(toggle_btn_text,      f"s_tg_cat_{cat_id}"),
    ])

    for m in methods:
        ms   = s.methods[m.id]
        icon = "✅" if ms.enabled else "☐"
        name = method_name(m.id, lang, fallback=m.name)
        int_str = "" if m.param_type == PARAM_ONOFF else f" {ms.intensity}%"
        rows.append([_btn(
            f"{icon} {m.id}. {name}{int_str} {ms.frequency}%",
            f"s_met_{m.id}",
        )])

    rows.append([_btn(t("btn_back", lang), "s_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_method(method_id: int, s: UserSettings, lang: str) -> InlineKeyboardMarkup:
    m  = get_method(method_id)
    ms = s.methods[method_id]
    cat_id = m.category

    rows = []

    # Back
    rows.append([_btn(f"◀️ {cat_id}", f"s_cat_{cat_id}")])

    # Toggle
    if ms.enabled:
        tog_text = t("method_on", lang)
    else:
        tog_text = t("method_off", lang)
    rows.append([_btn(tog_text, f"s_tg_{method_id}")])

    # Frequency row — geometry methods (cat 1) always apply, no frequency control
    if m.category != 1:
        freq = ms.frequency
        rows.append([
            _btn("−10%", f"s_frq_{method_id}_dn"),
            _btn(f"{freq}%", f"s_frq_{method_id}_noop"),
            _btn("+10%", f"s_frq_{method_id}_up"),
            _btn("100%", f"s_frq_{method_id}_max"),
        ])

    # Intensity row (only for non-ONOFF methods)
    if m.param_type != PARAM_ONOFF:
        real = get_real_label(method_id, ms.intensity)
        val_label = f" → {real}" if real else ""
        rows.append([
            _btn("−10", f"s_int_{method_id}_dn"),
            _btn(f"⚡ {ms.intensity}%{val_label}", f"s_int_{method_id}_noop"),
            _btn("+10", f"s_int_{method_id}_up"),
            _btn("✏️", f"s_int_{method_id}_edit"),
        ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


# ════════════════════════════════════════════════════════════════════════════
# Command entry point
# ════════════════════════════════════════════════════════════════════════════

@router.message(Command("settings"))
async def cmd_settings(message: Message):
    s = UserSettings.load(message.from_user.id)
    lang = s.language
    active = sum(1 for ms in s.methods.values() if ms.enabled)
    if s.global_enabled:
        g_str = t("settings_on", lang)
    else:
        g_str = t("settings_off", lang)
    await message.answer(
        t("settings_title", lang, g_str=g_str, active=active, total=TOTAL_METHODS),
        parse_mode="HTML",
        reply_markup=kb_main(s, lang),
    )


# ════════════════════════════════════════════════════════════════════════════
# Callbacks
# ════════════════════════════════════════════════════════════════════════════

def _has_pending(user_id: int) -> bool:
    from bot.handlers.video import has_pending_video
    return has_pending_video(user_id)


async def _edit_main(cb: CallbackQuery, s: UserSettings, lang: str) -> None:
    active = sum(1 for ms in s.methods.values() if ms.enabled)
    if s.global_enabled:
        g_str = t("settings_on", lang)
    else:
        g_str = t("settings_off", lang)
    await cb.message.edit_text(
        t("settings_title", lang, g_str=g_str, active=active, total=TOTAL_METHODS),
        parse_mode="HTML",
        reply_markup=kb_main(s, lang, has_pending_video=_has_pending(cb.from_user.id)),
    )


# ── Main menu ─────────────────────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "s_main")
async def cb_main(cb: CallbackQuery):
    s = UserSettings.load(cb.from_user.id)
    lang = s.language
    await _edit_main(cb, s, lang)
    await cb.answer()


# ── Close ─────────────────────────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "s_close")
async def cb_close(cb: CallbackQuery):
    await cb.message.delete()
    await cb.answer()


# ── Export from settings menu ────────────────────────────────────────────────────────────
@router.callback_query(F.data == "s_exp")
async def cb_export(cb: CallbackQuery):
    from aiogram.types import BufferedInputFile
    s = UserSettings.load(cb.from_user.id)
    lang = s.language
    buf = BufferedInputFile(s.export_json().encode("utf-8"), filename="settings.json")
    await cb.message.answer_document(buf, caption=t("exported", lang))
    await cb.answer()


# ── Global toggle ───────────────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "s_tg_gl")
async def cb_toggle_global(cb: CallbackQuery):
    s = UserSettings.load(cb.from_user.id)
    lang = s.language
    s.global_enabled = not s.global_enabled
    s.save()
    await _edit_main(cb, s, lang)
    if s.global_enabled:
        answer_text = t("toggled_on", lang)
    else:
        answer_text = t("toggled_off", lang)
    await cb.answer(answer_text)


# ── Category toggle ──────────────────────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("s_tg_cat_"))
async def cb_toggle_category(cb: CallbackQuery):
    cat_id = int(cb.data.split("_")[-1])
    s = UserSettings.load(cb.from_user.id)
    lang = s.language
    new_state = s.toggle_category(cat_id)
    s.save()
    await cb.message.edit_reply_markup(reply_markup=kb_category(cat_id, s, lang))
    if new_state:
        answer_text = t("all_enabled", lang)
    else:
        answer_text = t("all_disabled", lang)
    await cb.answer(answer_text)


# ── Category view ─────────────────────────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("s_cat_"))
async def cb_category(cb: CallbackQuery):
    cat_id = int(cb.data.split("_")[-1])
    s      = UserSettings.load(cb.from_user.id)
    lang   = s.language
    emoji, _ = CATEGORY_NAMES[cat_id]
    name     = cat_name(cat_id, lang)
    en, tot  = s.category_enabled_count(cat_id)
    hint = CATEGORY_HINTS.get(lang, CATEGORY_HINTS["en"]).get(cat_id, "")

    await cb.message.edit_text(
        f"⚙️ <b>{emoji} {name}</b>  ({en}/{tot})\n<i>{hint}</i>" + t("cat_hint", lang),
        parse_mode="HTML",
        reply_markup=kb_category(cat_id, s, lang),
    )
    await cb.answer()


# ── Method detail ─────────────────────────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("s_met_"))
async def cb_method(cb: CallbackQuery):
    mid = int(cb.data.split("_")[-1])
    m   = get_method(mid)
    s   = UserSettings.load(cb.from_user.id)
    lang = s.language
    ms  = s.methods[mid]

    status_icon = "✅" if ms.enabled else "⬜"
    if ms.enabled:
        status_text = t("method_on", lang)
    else:
        status_text = t("method_off", lang)

    int_str = ""
    if m.param_type != PARAM_ONOFF:
        real = get_real_label(mid, ms.intensity)
        bar = intensity_bar(ms.intensity)
        lbl = f"{real} ({ms.intensity}%)" if real else f"{ms.intensity}%"
        int_str = t("method_intensity", lang, label=lbl, bar=bar)

    if m.category == 1:
        freq_str = t("method_freq_always", lang)
    else:
        freq_str = t("method_freq", lang, freq=ms.frequency)

    display_name = method_name(m.id, lang, fallback=m.name)
    text = (
        f"{status_icon} <b>{display_name}</b>\n"
        f"<i>{m.description}</i>\n\n"
        f"{status_text}"
        f"{freq_str}"
        f"{int_str}"
    )
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb_method(mid, s, lang))
    await cb.answer()


# ── Method toggle ─────────────────────────────────────────────────────────────
@router.callback_query(F.data.regexp(r"^s_tg_\d+$"))
async def cb_toggle_method(cb: CallbackQuery):
    mid = int(cb.data.split("_")[-1])
    s   = UserSettings.load(cb.from_user.id)
    lang = s.language
    new = s.toggle_method(mid)
    s.save()
    m  = get_method(mid)
    ms = s.methods[mid]

    status_icon = "✅" if ms.enabled else "⬜"
    status_text = t("method_on", lang) if ms.enabled else t("method_off", lang)

    int_str = ""
    if m.param_type != PARAM_ONOFF:
        real = get_real_label(mid, ms.intensity)
        bar = intensity_bar(ms.intensity)
        lbl = f"{real} ({ms.intensity}%)" if real else f"{ms.intensity}%"
        int_str = t("method_intensity", lang, label=lbl, bar=bar)

    display_name = method_name(m.id, lang, fallback=m.name)
    if m.category == 1:
        freq_line = t("method_freq_always", lang)
    else:
        freq_line = t("method_freq", lang, freq=ms.frequency)
    text = (
        f"{status_icon} <b>{display_name}</b>\n"
        f"<i>{m.description}</i>\n\n"
        f"{status_text}\n"
        + freq_line
        + int_str
    )
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb_method(mid, s, lang))
    await cb.answer(t("toggled_on", lang) if new else t("toggled_off", lang))


# ── Intensity ±10 / edit ──────────────────────────────────────────────────────
_awaiting_intensity: dict[int, int] = {}  # user_id → method_id

@router.callback_query(F.data.regexp(r"^s_int_\d+_(up|dn|noop|edit)$"))
async def cb_intensity(cb: CallbackQuery):
    parts = cb.data.split("_")
    mid   = int(parts[2])
    cmd   = parts[3]

    if cmd == "noop":
        await cb.answer()
        return

    s    = UserSettings.load(cb.from_user.id)
    lang = s.language

    if cmd == "edit":
        _awaiting_intensity[cb.from_user.id] = mid
        await cb.answer(t("intensity_type", lang), show_alert=True)
        return

    ms = s.methods[mid]
    delta = 10 if cmd == "up" else -10
    s.set_intensity(mid, max(1, min(100, ms.intensity + delta)))
    s.save()

    real = get_real_label(mid, s.methods[mid].intensity)
    lbl = f"{real} ({s.methods[mid].intensity}%)" if real else f"{s.methods[mid].intensity}%"
    await cb.message.edit_reply_markup(reply_markup=kb_method(mid, s, lang))
    await cb.answer(t("intensity_set", lang, label=lbl))


@router.message(F.text.regexp(r"^\d{1,3}$"))
async def on_intensity_typed(message: Message):
    uid = message.from_user.id
    if uid not in _awaiting_intensity:
        return  # not waiting for input, ignore
    mid = _awaiting_intensity.pop(uid)
    val = int(message.text)
    val = max(1, min(100, val))

    s = UserSettings.load(uid)
    lang = s.language
    s.set_intensity(mid, val)
    s.save()

    m = get_method(mid)
    real = get_real_label(mid, val)
    lbl = f"{real} ({val}%)" if real else f"{val}%"
    name = method_name(m.id, lang, fallback=m.name)
    await message.reply(f"⚡ {name}: {lbl}", parse_mode="HTML")


# ── Frequency ±10 / 100% ────────────────────────────────────────────────────
@router.callback_query(F.data.regexp(r"^s_frq_\d+_(up|dn|max|noop)$"))
async def cb_frequency(cb: CallbackQuery):
    parts = cb.data.split("_")
    mid   = int(parts[2])
    cmd   = parts[3]

    if cmd == "noop":
        await cb.answer()
        return

    s  = UserSettings.load(cb.from_user.id)
    lang = s.language
    ms = s.methods[mid]

    if cmd == "max":
        ms.frequency = 100
    else:
        delta = 10 if cmd == "up" else -10
        ms.frequency = max(0, min(100, ms.frequency + delta))
    s.save()

    await cb.message.edit_reply_markup(reply_markup=kb_method(mid, s, lang))
    await cb.answer(t("frequency_set", lang, freq=ms.frequency))
