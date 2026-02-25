"""
Preset selection handler — presets + specialized templates.
"""
from __future__ import annotations

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from bot.i18n import t
from bot.models.user_settings import UserSettings
from bot.processors.methods import PRESETS, ALL_METHODS

logger = logging.getLogger(__name__)
router = Router()


# ── Preset keys & emojis (language-independent) ──────────────────────────────

PRESET_KEYS = ["light", "medium", "iphone", "aggressive", "maximum"]
PRESET_EMOJI = {
    "light": "🟢", "medium": "🟡", "iphone": "📱",
    "aggressive": "🟠", "maximum": "🔴",
}


def _preset_name(key: str, lang: str) -> str:
    return t(f"preset_{key}", lang)


def _preset_desc(key: str, lang: str) -> str:
    return t(f"preset_{key}_desc", lang)


# ── Specialized templates ─────────────────────────────────────────────────────

TEMPLATE_DEFS = {
    "tpl_codec":        ("🔧", {7}),
    "tpl_visual":       ("🎨", {1, 2, 3, 4, 8, 9}),
    "tpl_audio":        ("🔊", {6}),
    "tpl_meta":         ("🏷",  {7}),       # special: only methods 50, 51
    "tpl_soft":         ("🕊",  {6, 7}),
    "tpl_full_noaudio": ("🎬", {1, 2, 3, 4, 5, 7, 8, 9}),
}


def _tpl_name(tpl_id: str, lang: str) -> str:
    return t(f"{tpl_id}_name", lang)


def _tpl_desc(tpl_id: str, lang: str) -> str:
    return t(f"{tpl_id}_desc", lang)


def _tpl_emoji(tpl_id: str) -> str:
    return TEMPLATE_DEFS[tpl_id][0]


def _tpl_cats(tpl_id: str) -> set:
    return TEMPLATE_DEFS[tpl_id][1]


def _build_template_settings(template_id: str) -> dict:
    """Returns dict {method_id: {enabled, intensity, frequency}} for a template."""
    enabled_cats = _tpl_cats(template_id)
    result = {}
    meta_only = template_id == "tpl_meta"

    for m in ALL_METHODS:
        if meta_only:
            en = m.id in {50, 51}
        else:
            en = m.category in enabled_cats

        result[str(m.id)] = {
            "enabled":   en,
            "intensity": 30,
            "frequency": 90 if en else 0,
        }
    return result


# ── Keyboards ─────────────────────────────────────────────────────────────────

def kb_presets(lang: str, custom_names: list[str] | None = None) -> InlineKeyboardMarkup:
    rows = []

    # Standard presets
    rows.append([InlineKeyboardButton(text=t("hdr_levels", lang), callback_data="pre_noop")])
    for key in PRESET_KEYS:
        emoji = PRESET_EMOJI[key]
        label = _preset_name(key, lang)
        desc = _preset_desc(key, lang)
        rows.append([InlineKeyboardButton(
            text=f"{emoji}  {label}  —  {desc}",
            callback_data=f"pre_apply_{key}",
        )])

    # Specialized templates
    rows.append([InlineKeyboardButton(text=t("hdr_templates", lang), callback_data="pre_noop")])
    for tpl_id in TEMPLATE_DEFS:
        emoji = _tpl_emoji(tpl_id)
        name = _tpl_name(tpl_id, lang)
        rows.append([InlineKeyboardButton(
            text=f"{emoji}  {name}",
            callback_data=f"pre_tpl_{tpl_id}",
        )])

    # Custom presets
    if custom_names:
        rows.append([InlineKeyboardButton(text=t("hdr_my_presets", lang), callback_data="pre_noop")])
        for name in custom_names[:5]:
            rows.append([
                InlineKeyboardButton(text=f"🔖 {name}",               callback_data=f"pre_apply_c_{name[:20]}"),
                InlineKeyboardButton(text=t("btn_delete_preset", lang), callback_data=f"pre_del_{name[:20]}"),
            ])

    rows.append([InlineKeyboardButton(text=t("btn_save_preset", lang), callback_data="pre_save")])
    rows.append([InlineKeyboardButton(text=t("btn_back_settings", lang), callback_data="s_main")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def _presets_text(lang: str) -> str:
    lines = [t("presets_title", lang)]

    lines.append(t("presets_levels", lang))
    for key in PRESET_KEYS:
        emoji = PRESET_EMOJI[key]
        label = _preset_name(key, lang)
        desc = _preset_desc(key, lang)
        lines.append(f"{emoji} <b>{label}</b> — {desc}")

    lines.append(t("presets_templates", lang))
    for tpl_id in TEMPLATE_DEFS:
        emoji = _tpl_emoji(tpl_id)
        name = _tpl_name(tpl_id, lang)
        desc = _tpl_desc(tpl_id, lang).split("\n")[0]
        lines.append(f"{emoji} <b>{name}</b>\n<i>{desc}</i>")

    return "\n".join(lines)


# ── Commands ─────────────────────────────────────────────────────────────────

@router.message(Command("preset"))
async def cmd_preset(message: Message):
    s = UserSettings.load(message.from_user.id)
    lang = s.language
    custom_names = list(s.custom_presets.keys())
    await message.answer(
        _presets_text(lang),
        parse_mode="HTML",
        reply_markup=kb_presets(lang, custom_names),
    )


@router.callback_query(F.data == "pre_menu")
async def cb_preset_menu(cb: CallbackQuery):
    s = UserSettings.load(cb.from_user.id)
    lang = s.language
    custom_names = list(s.custom_presets.keys())
    await cb.message.edit_text(
        _presets_text(lang),
        parse_mode="HTML",
        reply_markup=kb_presets(lang, custom_names),
    )
    await cb.answer()


# ── Apply custom preset ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("pre_apply_c_"))
async def cb_apply_custom(cb: CallbackQuery):
    name = cb.data[len("pre_apply_c_"):]
    s    = UserSettings.load(cb.from_user.id)
    lang = s.language
    if name not in s.custom_presets:
        await cb.answer(t("preset_not_found", lang), show_alert=True)
        return
    s.apply_preset(name)
    s.save()
    active = sum(1 for ms in s.methods.values() if ms.enabled)
    await cb.answer(t("preset_applied", lang, emoji="✅", label=name, active=active))


# ── Apply standard preset ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("pre_apply_"))
async def cb_apply_preset(cb: CallbackQuery):
    key = cb.data[len("pre_apply_"):]
    if key not in PRESETS:
        s = UserSettings.load(cb.from_user.id)
        await cb.answer(t("preset_unknown", s.language), show_alert=True)
        return
    s = UserSettings.load(cb.from_user.id)
    lang = s.language
    s.apply_preset(key)
    s.save()
    emoji = PRESET_EMOJI[key]
    label = _preset_name(key, lang)
    active = sum(1 for ms in s.methods.values() if ms.enabled)
    await cb.answer(t("preset_applied", lang, emoji=emoji, label=label, active=active))

    custom_names = list(s.custom_presets.keys())
    try:
        await cb.message.edit_text(
            _presets_text(lang) + t("preset_applied_inline", lang, emoji=emoji, label=label, active=active),
            parse_mode="HTML",
            reply_markup=kb_presets(lang, custom_names),
        )
    except Exception:
        pass


# ── Apply specialized template ───────────────────────────────────────────────

@router.callback_query(F.data.startswith("pre_tpl_"))
async def cb_apply_template(cb: CallbackQuery):
    tpl_id = cb.data[len("pre_tpl_"):]
    if tpl_id not in TEMPLATE_DEFS:
        s = UserSettings.load(cb.from_user.id)
        await cb.answer(t("template_not_found", s.language), show_alert=True)
        return

    s = UserSettings.load(cb.from_user.id)
    lang = s.language
    emoji = _tpl_emoji(tpl_id)
    name = _tpl_name(tpl_id, lang)
    desc = _tpl_desc(tpl_id, lang)

    # Apply template
    cfg = _build_template_settings(tpl_id)
    s.import_json('{"global_enabled": true, "methods": ' +
                  str(cfg).replace("'", '"').replace("True", "true").replace("False", "false") + '}')
    s.save()

    active = sum(1 for ms in s.methods.values() if ms.enabled)
    await cb.answer(t("template_applied", lang, emoji=emoji, name=name, active=active))

    custom_names = list(s.custom_presets.keys())
    short_desc = desc.split("\n")[0]
    try:
        await cb.message.edit_text(
            _presets_text(lang) + t("template_applied_inline", lang, emoji=emoji, name=name, desc=short_desc, active=active),
            parse_mode="HTML",
            reply_markup=kb_presets(lang, custom_names),
        )
    except Exception:
        pass


# ── Delete preset ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("pre_del_"))
async def cb_delete_preset(cb: CallbackQuery):
    name = cb.data[len("pre_del_"):]
    s    = UserSettings.load(cb.from_user.id)
    lang = s.language
    s.delete_custom_preset(name)
    custom_names = list(s.custom_presets.keys())
    try:
        await cb.message.edit_text(
            _presets_text(lang),
            parse_mode="HTML",
            reply_markup=kb_presets(lang, custom_names),
        )
    except Exception:
        await cb.message.edit_reply_markup(reply_markup=kb_presets(lang, custom_names))
    await cb.answer(t("preset_deleted", lang, name=name))


# ── Save preset ──────────────────────────────────────────────────────────────

_awaiting_preset_name: dict[int, bool] = {}   # user_id → True when waiting for name

@router.callback_query(F.data == "pre_save")
async def cb_save_preset(cb: CallbackQuery):
    s = UserSettings.load(cb.from_user.id)
    lang = s.language
    _awaiting_preset_name[cb.from_user.id] = True
    await cb.message.answer(t("preset_save_prompt", lang), parse_mode="HTML")
    await cb.answer()


@router.message(F.text)
async def on_preset_name_typed(message: Message):
    uid = message.from_user.id
    if uid not in _awaiting_preset_name:
        return  # not waiting for preset name, skip
    del _awaiting_preset_name[uid]

    s = UserSettings.load(uid)
    lang = s.language

    name = message.text.strip()[:20]
    if not name:
        await message.reply(t("preset_name_empty", lang))
        return

    s.save_custom_preset(name)

    custom_names = list(s.custom_presets.keys())
    active = sum(1 for ms in s.methods.values() if ms.enabled)
    await message.answer(
        t("preset_saved", lang, name=name, active=active) + "\n\n" + _presets_text(lang),
        parse_mode="HTML",
        reply_markup=kb_presets(lang, custom_names),
    )


@router.callback_query(F.data == "pre_noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()
