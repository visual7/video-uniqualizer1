"""
Definitions of all uniqualization methods.
Each method knows its category, display name, parameter type,
and default settings.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


# ── Parameter types ────────────────────────────────────────────────────────────
PARAM_ONOFF     = "onoff"       # no intensity, just enabled/disabled
PARAM_INTENSITY = "intensity"   # intensity 1-100%


# ── Category metadata ──────────────────────────────────────────────────────────
CATEGORY_NAMES = {
    1: ("📐", "Геометрические"),
    2: ("🎨", "Цветокоррекция"),
    3: ("🔍", "Резкость"),
    4: ("🌪",  "Шум"),
    5: ("⏱",  "Временные"),
    6: ("🔊", "Аудио"),
    7: ("💾", "Кодирование"),
    8: ("🖼",  "Наложения"),
    9: ("⚡", "Продвинутые"),
}


@dataclass
class Method:
    id:                int
    category:          int
    name:              str
    description:       str
    param_type:        str          # PARAM_ONOFF | PARAM_INTENSITY
    default_enabled:   bool = True
    default_intensity: int  = 50    # 1-100%
    default_frequency: int  = 50    # 0-100 %


# ── ALL 49 METHODS ─────────────────────────────────────────────────────────────
ALL_METHODS: List[Method] = [
    # ── Category 1: Geometric (11) ───────────────────────────────────────────
    Method(1,  1, "Зеркало ←→",            "Отражает видео слева направо (как в зеркале)",       PARAM_ONOFF,     True,  3, 100),
    Method(2,  1, "Зеркало ↑↓",            "Переворачивает видео вверх ногами",                  PARAM_ONOFF,     False, 3, 100),
    Method(3,  1, "Поворот",               "Поворачивает картинку на небольшой угол",            PARAM_INTENSITY, True,  30, 100),
    Method(4,  1, "Наклон",                "Наклоняет картинку вбок, как если камера чуть криво", PARAM_INTENSITY, True,  30, 100),
    Method(5,  1, "Обрезка краёв",         "Срезает края видео со всех сторон",                  PARAM_INTENSITY, True,  30, 100),
    Method(6,  1, "Зум",                   "Приближает картинку (как зум на камере)",            PARAM_INTENSITY, True,  30, 100),
    Method(7,  1, "Сдвиг картинки",        "Двигает картинку влево/вправо/вверх/вниз",          PARAM_INTENSITY, True,  30, 100),
    Method(8,  1, "Перспектива",           "Как будто смотришь на экран чуть сбоку",             PARAM_INTENSITY, False, 30, 100),
    Method(9,  1, "Чёрные полосы",         "Добавляет полосы сверху/снизу (как в кино)",         PARAM_INTENSITY, True,  30, 100),
    Method(69, 1, "3D сдвиг ←→",          "Как будто камера сдвинулась влево или вправо",       PARAM_INTENSITY, True,  30, 100),
    Method(70, 1, "3D сдвиг ↑↓",          "Как будто камера сдвинулась вверх или вниз",         PARAM_INTENSITY, True,  30, 100),

    # ── Category 2: Color (9) ────────────────────────────────────────────────
    Method(10, 2, "Яркость",               "Делает видео чуть светлее или темнее",              PARAM_INTENSITY, True,  15, 80),
    Method(11, 2, "Контрастность",         "Усиливает или ослабляет разницу светлого и тёмного", PARAM_INTENSITY, True,  15, 70),
    Method(12, 2, "Насыщенность",          "Делает цвета ярче или бледнее",                     PARAM_INTENSITY, True,  15, 70),
    Method(13, 2, "Оттенок (hue)",         "Сдвигает все цвета по кругу (красный→оранж и т.д.)", PARAM_INTENSITY, True, 10, 60),
    Method(14, 2, "Гамма-коррекция",       "Меняет яркость средних тонов (тени/света)",         PARAM_INTENSITY, True,  10, 60),
    Method(15, 2, "Баланс белого",         "Делает картинку теплее или холоднее",               PARAM_INTENSITY, True,  10, 50),
    Method(17, 2, "Кривые (curves)",       "Тонкая подстройка цветов через RGB-кривые",        PARAM_INTENSITY, True,  10, 50),
    Method(19, 2, "Виньетирование",        "Затемняет углы кадра (как в Инстаграм-фильтре)",   PARAM_INTENSITY, True,  10, 60),
    Method(20, 2, "Цветовой шум",          "Добавляет мелкую цветную рябь",                    PARAM_INTENSITY, True,  8, 50),

    # ── Category 3: Sharpness (3) ────────────────────────────────────────────
    Method(21, 3, "Резкость (sharpen)",    "Делает картинку чётче (видно на деталях/тексте)",  PARAM_INTENSITY, True,  15, 60),
    Method(23, 3, "Unsharp mask",          "Подчёркивает контуры и мелкие детали",             PARAM_INTENSITY, True,  12, 50),
    Method(24, 3, "Выборочная резкость",   "Добавляет резкость только в центре кадра",         PARAM_INTENSITY, False, 10, 30),

    # ── Category 4: Noise (2) ────────────────────────────────────────────────
    Method(27, 4, "Зернистость плёнки",    "Добавляет зерно как на старой плёнке",             PARAM_INTENSITY, True,  8, 60),
    Method(28, 4, "Случайный шум",         "Добавляет мелкий шум на картинку",                 PARAM_INTENSITY, True,  8, 60),

    # ── Category 5: Temporal (3) ─────────────────────────────────────────────
    Method(33, 5, "Изменение FPS",         "Меняет кол-во кадров/сек (30→29 и т.д.)",         PARAM_INTENSITY, True,  8, 60),
    Method(34, 5, "Скорость видео",        "Чуть ускоряет или замедляет видео",                PARAM_INTENSITY, True,  8, 50),
    Method(37, 5, "Подрезка нач./конца",   "Обрезает первые/последние доли секунды",           PARAM_INTENSITY, True,  8, 70),

    # ── Category 6: Audio (5) ────────────────────────────────────────────────
    Method(41, 6, "Эквалайзер",            "Чуть меняет баланс частот (басы/верха)",           PARAM_INTENSITY, True,  10, 60),
    Method(42, 6, "Аудио-шум",             "Добавляет еле слышный фоновый шум",               PARAM_INTENSITY, True,  8, 50),
    Method(44, 6, "Рекодирование аудио",   "Пересжимает звук другим кодеком",                 PARAM_INTENSITY, True,  10, 80),
    Method(45, 6, "Стерео-сдвиг",         "Чуть сдвигает звук влево или вправо",             PARAM_INTENSITY, True,  8, 40),
    Method(46, 6, "Нормализация громк.",   "Выравнивает громкость до стандарта",               PARAM_INTENSITY, True,  10, 70),

    # ── Category 7: Encoding (8) ─────────────────────────────────────────────
    Method(47, 7, "Перекодировка видео",   "Пересжимает видео другим кодеком",               PARAM_INTENSITY, True,  10, 90),
    Method(48, 7, "Изменение битрейта",    "Меняет качество сжатия (размер файла)",          PARAM_INTENSITY, True,  10, 80),
    Method(49, 7, "Смена контейнера",      "Меняет формат файла (mp4→mkv и т.д.)",           PARAM_ONOFF,     False, 3, 30),
    Method(50, 7, "Очистка метаданных",    "Стирает всю скрытую информацию из файла",        PARAM_ONOFF,     True,  3, 100),
    Method(51, 7, "Новые метаданные",      "Вшивает фейковые данные iPhone/CapCut",          PARAM_ONOFF,     True,  3, 90),
    Method(52, 7, "Изменение GOP",         "Меняет структуру ключевых кадров",               PARAM_INTENSITY, True,  10, 70),
    Method(53, 7, "Pixel format",          "Меняет внутренний формат цвета",                 PARAM_INTENSITY, False, 5, 40),
    Method(54, 7, "Стеганогр. метка",      "Прячет уникальный код в пикселях (невидимо)",    PARAM_ONOFF,     True,  3, 80),

    # ── Category 8: Overlays (4) ─────────────────────────────────────────────
    Method(55, 8, "Невид. водяной знак",   "Прозрачный знак поверх видео (не видно глазом)", PARAM_INTENSITY, True,  5, 50),
    Method(58, 8, "Скрытый пиксель",       "Меняет несколько случайных пикселей (невидимо)", PARAM_INTENSITY, True,  5, 80),
    Method(59, 8, "Лёгкая виньетка",       "Чуть затемняет углы кадра",                     PARAM_INTENSITY, True,  8, 50),
    Method(60, 8, "Субпиксельный сдвиг",   "Микросдвиг картинки (невидимо, но меняет хеш)", PARAM_INTENSITY, True,  5, 60),

    # ── Category 9: Advanced (4) ─────────────────────────────────────────────
    Method(61, 9, "Случайный seed",        "Каждая копия уникальна за счёт случайного зерна", PARAM_ONOFF,    True,  3, 100),
    Method(62, 9, "Пикс. интерполяция",    "Пересчитывает пиксели другим алгоритмом",        PARAM_INTENSITY, True,  8, 70),
    Method(63, 9, "Локальные деформации",  "Чуть двигает случайные участки кадра",            PARAM_INTENSITY, False, 5, 20),
    Method(64, 9, "DCT-модификация",       "Меняет внутреннее сжатие кадров",                 PARAM_INTENSITY, False, 5, 20),
]

TOTAL_METHODS = len(ALL_METHODS)  # 49

# ── Lookup helpers ─────────────────────────────────────────────────────────────
_BY_ID: Dict[int, Method] = {m.id: m for m in ALL_METHODS}

def get_method(method_id: int) -> Optional[Method]:
    return _BY_ID.get(method_id)

def get_methods_by_category(cat_id: int) -> List[Method]:
    return [m for m in ALL_METHODS if m.category == cat_id]

ALL_CATEGORIES = sorted(CATEGORY_NAMES.keys())


# ── Real-unit ranges for dynamic label computation ───────────────────────────
# Maps method_id → (lo, hi, format_str)
# Values must match intensity_val(_, lo, hi) in ffmpeg_builder.py
METHOD_RANGES: Dict[int, tuple] = {
    # Geometry
    3:  (0.3, 5, "±{v:.1f}°"),    4:  (0.2, 2, "±{v:.1f}°"),
    5:  (0.3, 4, "{v:.1f}%"),     6:  (0.5, 4, "{v:.1f}%"),
    7:  (0.3, 2, "±{v:.1f}%"),    8:  (2, 15, "{v:.0f}px"),
    9:  (0.5, 2, "{v:.1f}%"),
    69: (2, 12, "{v:.0f}px"),     70: (2, 12, "{v:.0f}px"),
    # Color
    10: (2, 12, "±{v:.1f}%"),    11: (2, 10, "±{v:.0f}%"),
    12: (3, 12, "±{v:.0f}%"),    13: (0.5, 6, "±{v:.1f}°"),
    14: (0.05, 0.15, "±{v:.2f}"), 15: (200, 800, "±{v:.0f}K"),
    17: (1, 4, "±{v:.1f}%"),
    19: (0.1, 0.4, "{v:.2f}"),
    20: (3, 15, "{v:.0f}"),
    # Sharpness
    21: (0.1, 0.7, "{v:.2f}"),
    23: (20, 100, "{v:.0f}"),    24: (0.1, 0.5, "{v:.2f}"),
    # Noise
    27: (1, 8, "{v:.0f}"),       28: (3, 12, "{v:.0f}"),
    # Temporal
    33: (1, 3, "±{v:.1f}"),      34: (2, 5, "±{v:.0f}%"),
    37: (50, 500, "{v:.0f}мс"),
    # Audio
    41: (1, 3, "±{v:.0f}dB"),    42: (0.001, 0.008, "{v:.4f}"),
    # Encoding
    48: (10, 25, "±{v:.0f}%"),   52: (25, 90, "{v:.0f}"),
    # Overlays
    55: (3, 8, "{v:.0f}%α"),
    59: (0.15, 0.4, "{v:.2f}"),
    60: (0.5, 3, "{v:.0f}px"),
}


def get_real_label(method_id: int, intensity: int) -> str:
    """Compute real-unit label dynamically from intensity percentage (1-100)."""
    info = METHOD_RANGES.get(method_id)
    if not info:
        return ""
    lo, hi, fmt = info
    t = max(0.0, min(1.0, (intensity - 1) / 99.0))
    v = lo + (hi - lo) * t
    return fmt.format(v=v)


# ── Built-in presets ──────────────────────────────────────────────────────────
# Preset format: {method_id: {enabled, intensity, frequency}}
def _build_preset(
    enabled_ids: list[int],
    intensity: int,
    freq_enabled: int,
    freq_disabled: int = 0,
) -> dict:
    result = {}
    for m in ALL_METHODS:
        is_enabled = m.id in enabled_ids
        # Geometry methods (cat 1) always freq=100 when enabled
        if m.category == 1 and is_enabled:
            freq = 100
        else:
            freq = freq_enabled if is_enabled else freq_disabled
        result[str(m.id)] = {
            "enabled":   is_enabled,
            "intensity": intensity,
            "frequency": freq,
        }
    return result

def _build_preset_custom(
    method_configs: dict[int, tuple[int, int]],
    base_intensity: int = 20,
    base_freq: int = 90,
) -> dict:
    """Build preset with per-method intensity/frequency overrides.
    method_configs: {method_id: (intensity, frequency)} for enabled methods.
    Methods not in method_configs are disabled.
    """
    result = {}
    for m in ALL_METHODS:
        if m.id in method_configs:
            inten, freq = method_configs[m.id]
            result[str(m.id)] = {
                "enabled": True,
                "intensity": inten,
                "frequency": freq,
            }
        else:
            result[str(m.id)] = {
                "enabled": False,
                "intensity": base_intensity,
                "frequency": 0,
            }
    return result


# ══════════════════════════════════════════════════════════════════════════════
# PRESETS
# ══════════════════════════════════════════════════════════════════════════════

# ── 🟢 Light — "Обход хеша" ──────────────────────────────────────────────
# ZERO visual / audible difference.  Changes: codec params, metadata,
# bitrate, GOP, hidden pixels.
PRESET_LIGHT_IDS = [
    47,  # Video re-encode
    48,  # Bitrate ±10-12%
    52,  # GOP / keyframe interval
    50,  # Clear old metadata
    51,  # New metadata (iPhone / CapCut fake)
    61,  # Random seed
    62,  # Pixel interpolation
    54,  # Steganographic LSB mark
    58,  # Hidden pixel (1-5 random pixels/frame)
    44,  # Audio re-encode
    46,  # Audio normalization
]

# ── 🟡 Medium — "Мягкая уникализация" ───────────────────────────────────
PRESET_MEDIUM_IDS = PRESET_LIGHT_IDS + [
    10,  # Brightness
    11,  # Contrast
    12,  # Saturation
    27,  # Film grain
    21,  # Sharpen
    55,  # Invisible text watermark
    33,  # FPS ±1
    37,  # Trim 50-80ms from start/end
]

# ── 🟠 Aggressive — "Заметная обработка" ─────────────────────────────────
PRESET_AGGRESSIVE_IDS = PRESET_MEDIUM_IDS + [
    60,  # Subpixel shift
    5,   # Crop edges
    6,   # Zoom
    3,   # Rotation
    69,  # Horizontal parallax
    70,  # Vertical parallax
    13,  # Hue
    14,  # Gamma
    17,  # Curves
    20,  # Chroma noise
    28,  # Random noise
    34,  # Speed
    41,  # Audio EQ
    45,  # Stereo shift
    59,  # Light vignette
]

# ── 🔴 Maximum — "Полная переработка" ────────────────────────────────────
PRESET_MAXIMUM_IDS = PRESET_AGGRESSIVE_IDS + [
    1,   # Horizontal mirror
    2,   # Vertical flip
    7,   # Frame shift
    8,   # Perspective warp
    9,   # Aspect padding
    15,  # White balance
    19,  # Vignette
    23,  # Unsharp mask
    24,  # Selective sharpen
    42,  # Audio noise
    49,  # Container change
    53,  # Pixel format
    63,  # Local warp
    64,  # DCT modification
    4,   # Skew
]

# ── 📱 iPhone — "Как на айфоне" ─────────────────────────────────────────
_IPHONE_METHODS = {
    # Hash evasion (invisible)
    47: (20, 100), 48: (20, 100), 52: (20, 100), 50: (20, 100),
    51: (20, 100), 61: (20, 100), 62: (20, 100), 54: (20, 100),
    58: (20, 100), 44: (20, 100), 46: (20, 100),
    # iPhone-style adjustments
    11: (25, 100),   # Contrast ≈ iPhone +15
    21: (50, 100),   # Sharpness ≈ iPhone 52
    59: (10, 100),   # Vignette ≈ iPhone 14
    3:  (16, 100),   # Rotation ≈ iPhone 1°
}
PRESET_IPHONE_IDS = list(_IPHONE_METHODS.keys())

# ── 🔒 Stealth — "Для клиента: минимальные отличия" ──────────────────────
# Invisble changes only. Each copy looks identical to the original,
# but has a unique hash, metadata, and pixel fingerprint.
# Designed for mass-producing 10-100 copies for TikTok/Reels bypass.
_STEALTH_METHODS = {
    # ── Core hash evasion (always on) ──
    47: (15, 100),   # Re-encode (CRF 18, no quality loss)
    48: (10, 100),   # Bitrate ±10% (barely changes file size)
    52: (15, 100),   # GOP change
    50: (15, 100),   # Clear metadata
    51: (15, 100),   # Fake iPhone/CapCut metadata
    61: (15, 100),   # Unique seed tag
    54: (15, 100),   # Steganographic LSB mark (invisible)
    58: (15, 100),   # Hidden pixel changes (invisible)
    62: (15, 100),   # Pixel interpolation (sub-pixel)
    # ── Micro color shifts (invisible at this intensity) ──
    10: (3, 100),    # Brightness ±0.02 (invisible)
    11: (3, 100),    # Contrast ±0.02 (invisible)
    12: (3, 100),    # Saturation ±0.03 (invisible)
    # ── Audio (inaudible) ──
    44: (15, 100),   # Audio re-encode
    42: (5, 100),    # Volume ±0.1% + highpass 15Hz (inaudible)
    46: (15, 100),   # Loudness normalization
    # ── Extras ──
    55: (5, 100),    # Invisible watermark (3% alpha)
    27: (3, 100),    # Film grain (strength 1, hides in compression)
    37: (3, 100),    # Trim 50ms from edges
}
PRESET_STEALTH_IDS = list(_STEALTH_METHODS.keys())

PRESETS = {
    "stealth":    _build_preset_custom(_STEALTH_METHODS),
    "light":      _build_preset(PRESET_LIGHT_IDS,      intensity=20,  freq_enabled=90),
    "medium":     _build_preset(PRESET_MEDIUM_IDS,     intensity=5,   freq_enabled=80),
    "iphone":     _build_preset_custom(_IPHONE_METHODS),
    "aggressive": _build_preset(PRESET_AGGRESSIVE_IDS, intensity=20,  freq_enabled=70),
    "maximum":    _build_preset([m.id for m in ALL_METHODS], intensity=60, freq_enabled=85),
}

PRESET_DISPLAY = {
    "stealth":    ("🔒", "Stealth",       f"{len(PRESET_STEALTH_IDS)} методов — невидимые отличия, максимальное сходство"),
    "light":      ("🟢", "Лёгкая",       f"{len(PRESET_LIGHT_IDS)} методов — обход хеша, метаданные"),
    "medium":     ("🟡", "Средняя",      f"{len(PRESET_MEDIUM_IDS)} методов — невидимые пиксельные изменения"),
    "iphone":     ("📱", "iPhone",       f"{len(PRESET_IPHONE_IDS)} методов — как на айфоне"),
    "aggressive": ("🟠", "Агрессивная",  f"{len(PRESET_AGGRESSIVE_IDS)} методов — геометрия + цветокоррекция"),
    "maximum":    ("🔴", "Максимальная", f"Все {TOTAL_METHODS} методов — полная переработка"),
}
