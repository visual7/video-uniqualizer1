"""
Preset selection handler — стандартные пресеты + специализированные шаблоны.
"""
from __future__ import annotations

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from bot.models.user_settings import UserSettings
from bot.processors.methods import PRESETS, ALL_METHODS

logger = logging.getLogger(__name__)
router = Router()


# ── Стандартные пресеты ────────────────────────────────────────────────────────

PRESET_INFO = {
    "light":      ("🟢", "Лёгкая",      "~11 методов — незаметно глазу"),
    "medium":     ("🟡", "Средняя",     "~19 методов — оптимальный баланс"),
    "iphone":     ("📱", "iPhone",      "~15 методов — как обработка на айфоне ⭐"),
    "aggressive": ("🟠", "Агрессивная", "~38 методов — максимальная уникальность"),
    "maximum":    ("🔴", "Максимальная","все 70 методов — полная обработка"),
}


# ── Специализированные шаблоны ─────────────────────────────────────────────────
# Каждый шаблон определяет: какие категории включить (остальные выключены)
# Формат: {template_id: (emoji, name, description, enabled_categories)}

TEMPLATE_DEFS = {
    "tpl_codec": (
        "🔧", "Только кодирование",
        "Меняет кодек, битрейт и метаданные — без изменения картинки и звука.\n"
        "Файл визуально идентичен, но имеет другой хеш.",
        {7},  # только категория 7 (кодирование)
    ),
    "tpl_visual": (
        "🎨", "Только визуал",
        "Цвет, геометрия, резкость, шум — без изменения звука и кодека.\n"
        "Аудиодорожка остаётся нетронутой.",
        {1, 2, 3, 4, 8, 9},
    ),
    "tpl_audio": (
        "🔊", "Только аудио",
        "Меняет только звуковую дорожку: тон, эквалайзер, громкость.\n"
        "Видеодорожка не трогается.",
        {6},
    ),
    "tpl_meta": (
        "🏷",  "Только метаданные",
        "Очищает оригинальные метаданные и заполняет случайными.\n"
        "Самый быстрый способ изменить хеш.",
        {7},  # только методы 50 и 51 из категории 7
    ),
    "tpl_soft": (
        "🕊",  "Мягкая (без артефактов)",
        "Только незаметные изменения: метаданные, кодирование, нормализация звука.\n"
        "Качество на 100% сохраняется.",
        {6, 7},
    ),
    "tpl_full_noaudio": (
        "🎬", "Визуал + кодек (без аудио)",
        "Все визуальные методы + кодирование, но аудио не трогается.",
        {1, 2, 3, 4, 5, 7, 8, 9},
    ),
}


def _build_template_settings(template_id: str) -> dict:
    """Возвращает dict {method_id: {enabled, intensity, frequency}} для шаблона."""
    _, _, _, enabled_cats = TEMPLATE_DEFS[template_id]
    result = {}

    # Особый случай: tpl_meta — только методы 50 (clear meta) и 51 (new meta)
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

def kb_presets(custom_names: list[str] | None = None) -> InlineKeyboardMarkup:
    rows = []

    # Стандартные пресеты
    rows.append([InlineKeyboardButton(text="── Уровни уникализации ──", callback_data="pre_noop")])
    for key, (emoji, label, desc) in PRESET_INFO.items():
        rows.append([InlineKeyboardButton(
            text=f"{emoji}  {label}  —  {desc}",
            callback_data=f"pre_apply_{key}",
        )])

    # Специализированные шаблоны
    rows.append([InlineKeyboardButton(text="── Специализированные шаблоны ──", callback_data="pre_noop")])
    for tpl_id, (emoji, name, _, _cats) in TEMPLATE_DEFS.items():
        rows.append([InlineKeyboardButton(
            text=f"{emoji}  {name}",
            callback_data=f"pre_tpl_{tpl_id}",
        )])

    # Пользовательские пресеты
    if custom_names:
        rows.append([InlineKeyboardButton(text="── Мои пресеты ──", callback_data="pre_noop")])
        for name in custom_names[:5]:
            rows.append([
                InlineKeyboardButton(text=f"🔖 {name}",     callback_data=f"pre_apply_c_{name[:20]}"),
                InlineKeyboardButton(text="🗑 удалить",     callback_data=f"pre_del_{name[:20]}"),
            ])

    rows.append([InlineKeyboardButton(text="💾 Сохранить текущие настройки как пресет", callback_data="pre_save")])
    rows.append([InlineKeyboardButton(text="◀️ К настройкам", callback_data="s_main")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def _presets_text() -> str:
    lines = ["🎨 <b>Пресеты и шаблоны уникализации</b>\n"]

    lines.append("<b>Уровни уникализации:</b>")
    for key, (emoji, label, desc) in PRESET_INFO.items():
        lines.append(f"{emoji} <b>{label}</b> — {desc}")

    lines.append("\n<b>Специализированные шаблоны:</b>")
    for tpl_id, (emoji, name, desc, _cats) in TEMPLATE_DEFS.items():
        short_desc = desc.split("\n")[0]
        lines.append(f"{emoji} <b>{name}</b>\n<i>{short_desc}</i>")

    return "\n".join(lines)


# ── Команды ───────────────────────────────────────────────────────────────────

@router.message(Command("preset"))
async def cmd_preset(message: Message):
    s = UserSettings.load(message.from_user.id)
    custom_names = list(s.custom_presets.keys())
    await message.answer(
        _presets_text(),
        parse_mode="HTML",
        reply_markup=kb_presets(custom_names),
    )


@router.callback_query(F.data == "pre_menu")
async def cb_preset_menu(cb: CallbackQuery):
    s = UserSettings.load(cb.from_user.id)
    custom_names = list(s.custom_presets.keys())
    await cb.message.edit_text(
        _presets_text(),
        parse_mode="HTML",
        reply_markup=kb_presets(custom_names),
    )
    await cb.answer()


# ── Применение стандартного пресета ──────────────────────────────────────────

@router.callback_query(F.data.startswith("pre_apply_c_"))
async def cb_apply_custom(cb: CallbackQuery):
    name = cb.data[len("pre_apply_c_"):]
    s    = UserSettings.load(cb.from_user.id)
    if name not in s.custom_presets:
        await cb.answer("❌ Пресет не найден.", show_alert=True)
        return
    s.apply_preset(name)
    s.save()
    active = sum(1 for ms in s.methods.values() if ms.enabled)
    await cb.answer(f"✅ Пресет «{name}» применён! Активных методов: {active}")


@router.callback_query(F.data.startswith("pre_apply_"))
async def cb_apply_preset(cb: CallbackQuery):
    key = cb.data[len("pre_apply_"):]
    if key not in PRESETS:
        await cb.answer("❌ Неизвестный пресет.", show_alert=True)
        return
    s = UserSettings.load(cb.from_user.id)
    s.apply_preset(key)
    s.save()
    emoji, label, _ = PRESET_INFO[key]
    active = sum(1 for ms in s.methods.values() if ms.enabled)
    await cb.answer(f"{emoji} Пресет «{label}» применён! Активных: {active}")

    custom_names = list(s.custom_presets.keys())
    try:
        await cb.message.edit_text(
            _presets_text() + f"\n\n{emoji} Применён: <b>{label}</b> ({active} методов)",
            parse_mode="HTML",
            reply_markup=kb_presets(custom_names),
        )
    except Exception:
        pass


# ── Применение специализированного шаблона ────────────────────────────────────

@router.callback_query(F.data.startswith("pre_tpl_"))
async def cb_apply_template(cb: CallbackQuery):
    tpl_id = cb.data[len("pre_tpl_"):]
    if tpl_id not in TEMPLATE_DEFS:
        await cb.answer("❌ Шаблон не найден.", show_alert=True)
        return

    emoji, name, desc, _cats = TEMPLATE_DEFS[tpl_id]
    s = UserSettings.load(cb.from_user.id)

    # Apply template
    cfg = _build_template_settings(tpl_id)
    s.import_json('{"global_enabled": true, "methods": ' +
                  str(cfg).replace("'", '"').replace("True", "true").replace("False", "false") + '}')
    s.save()

    active = sum(1 for ms in s.methods.values() if ms.enabled)
    await cb.answer(f"{emoji} Шаблон «{name}» применён! Активных: {active}")

    custom_names = list(s.custom_presets.keys())
    try:
        await cb.message.edit_text(
            _presets_text() + f"\n\n{emoji} Применён шаблон: <b>{name}</b>\n<i>{desc.split(chr(10))[0]}</i>\nАктивных методов: {active}",
            parse_mode="HTML",
            reply_markup=kb_presets(custom_names),
        )
    except Exception:
        pass


# ── Удаление пресета ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("pre_del_"))
async def cb_delete_preset(cb: CallbackQuery):
    name = cb.data[len("pre_del_"):]
    s    = UserSettings.load(cb.from_user.id)
    s.delete_custom_preset(name)
    custom_names = list(s.custom_presets.keys())
    try:
        await cb.message.edit_text(
            _presets_text(),
            parse_mode="HTML",
            reply_markup=kb_presets(custom_names),
        )
    except Exception:
        await cb.message.edit_reply_markup(reply_markup=kb_presets(custom_names))
    await cb.answer(f"🗑 Пресет «{name}» удалён.")


# ── Сохранение пресета ────────────────────────────────────────────────────────

_awaiting_preset_name: dict[int, bool] = {}   # user_id → True when waiting for name

@router.callback_query(F.data == "pre_save")
async def cb_save_preset(cb: CallbackQuery):
    _awaiting_preset_name[cb.from_user.id] = True
    await cb.message.answer(
        "💾 <b>Сохранение пресета</b>\n\n"
        "Введите название для пресета (до 20 символов):",
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(F.text)
async def on_preset_name_typed(message: Message):
    uid = message.from_user.id
    if uid not in _awaiting_preset_name:
        return  # not waiting for preset name, skip
    del _awaiting_preset_name[uid]

    name = message.text.strip()[:20]
    if not name:
        await message.reply("❌ Название не может быть пустым.")
        return

    s = UserSettings.load(uid)
    s.save_custom_preset(name)

    custom_names = list(s.custom_presets.keys())
    active = sum(1 for ms in s.methods.values() if ms.enabled)
    await message.answer(
        f"✅ Пресет «<b>{name}</b>» сохранён! ({active} методов)\n\n"
        + _presets_text(),
        parse_mode="HTML",
        reply_markup=kb_presets(custom_names),
    )


@router.callback_query(F.data == "pre_noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()
