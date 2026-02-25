"""
Internationalization — English (default) and Russian.
Usage:
    from bot.i18n import t, LANGUAGES
    text = t("welcome", lang)
"""
from __future__ import annotations

LANGUAGES = {
    "en": ("🇬🇧", "English"),
    "ru": ("🇷🇺", "Русский"),
}

# ── Category names ─────────────────────────────────────────────────────────────
CATEGORY_NAMES_I18N: dict[int, dict[str, str]] = {
    1: {"en": "Geometry",         "ru": "Геометрические"},
    2: {"en": "Color correction", "ru": "Цветокоррекция"},
    3: {"en": "Sharpness / Blur", "ru": "Резкость/Размытие"},
    4: {"en": "Noise & textures", "ru": "Шум и текстуры"},
    5: {"en": "Temporal",         "ru": "Временные"},
    6: {"en": "Audio",            "ru": "Аудио"},
    7: {"en": "Encoding",         "ru": "Кодирование"},
    8: {"en": "Overlays",         "ru": "Наложения"},
    9: {"en": "Advanced",         "ru": "Продвинутые"},
}

def cat_name(cat_id: int, lang: str) -> str:
    return CATEGORY_NAMES_I18N.get(cat_id, {}).get(lang) or CATEGORY_NAMES_I18N.get(cat_id, {}).get("en", "?")


# ── Method names (EN only — RU is in methods.py) ──────────────────────────────
METHOD_NAMES_EN: dict[int, str] = {
    1:  "Mirror ←→",           2:  "Mirror ↑↓",
    3:  "Rotation",            4:  "Tilt",
    5:  "Edge crop",           6:  "Zoom",
    7:  "Frame shift",         8:  "Perspective",
    9:  "Black bars",          10: "Brightness",
    11: "Contrast",            12: "Saturation",
    13: "Hue shift",           14: "Gamma correction",
    15: "White balance",       17: "Curves (RGB)",
    19: "Vignette",            20: "Chroma noise",
    21: "Sharpen",             23: "Unsharp mask",
    24: "Selective sharpen",   27: "Film grain",
    28: "Random noise",        33: "FPS change",
    34: "Video speed",         37: "Trim start/end",
    41: "Equalizer",           42: "Audio noise",
    44: "Audio re-encode",     45: "Stereo pan",
    46: "Loudness norm.",      47: "Video re-encode",
    48: "Bitrate change",      49: "Container change",
    50: "Clear metadata",      51: "Device metadata (iPhone/CapCut)",
    52: "GOP change",          53: "Pixel format",
    54: "Steganography mark",  55: "Invisible watermark",
    58: "Hidden pixel",        59: "Light vignette",
    60: "Subpixel shift",      61: "Random seed",
    62: "Pixel interpolation", 63: "Local warp",
    64: "DCT modification",    69: "3D shift ←→",
    70: "3D shift ↑↓",
}


def method_name(method_id: int, lang: str, fallback: str = "") -> str:
    if lang == "en":
        return METHOD_NAMES_EN.get(method_id, fallback)
    return fallback  # RU: use m.name from methods.py directly


# ── Intensity labels ──────────────────────────────────────────────────────────
INTENSITY_LABELS_I18N = {
    "en": {1: "Min", 2: "Low", 3: "Med", 4: "High", 5: "Max"},
    "ru": {1: "Мин", 2: "Низк", 3: "Средн", 4: "Высок", 5: "Макс"},
}

def intensity_label(level: int, lang: str) -> str:
    return INTENSITY_LABELS_I18N.get(lang, INTENSITY_LABELS_I18N["en"]).get(level, str(level))

_STRINGS: dict[str, dict[str, str]] = {

    # ── Language selection ─────────────────────────────────────────────────────
    "lang_select": {
        "en": "🌐 Choose your language:",
        "ru": "🌐 Выберите язык:",
    },
    "lang_set": {
        "en": "🇬🇧 Language set to English",
        "ru": "🇷🇺 Язык установлен: Русский",
    },

    # ── Welcome ────────────────────────────────────────────────────────────────
    "welcome": {
        "en": (
            "🎬 <b>Video Uniqueluzer</b>\n\n"
            "I create unique copies of your video — different hash, metadata\n"
            "and visual fingerprint. Quality stays the same.\n\n"
            "<b>How it works:</b>\n"
            "1️⃣ Send a video file (up to 2 GB) or a link\n"
            "2️⃣ Choose the uniqualization level\n"
            "3️⃣ Get the processed file"
        ),
        "ru": (
            "🎬 <b>Video Uniqueluzer</b>\n\n"
            "Делаю уникальные копии видео — с другим хешем, метаданными\n"
            "и визуальным отпечатком. Качество не страдает.\n\n"
            "<b>Как работает:</b>\n"
            "1️⃣ Отправь видеофайл (до 2 ГБ) или ссылку\n"
            "2️⃣ Выбери уровень уникализации\n"
            "3️⃣ Получи готовый файл"
        ),
    },
    "welcome_sub": {
        "en": "👇 Choose a preset or just send your video:",
        "ru": "👇 Выбери пресет или сразу отправь видео:",
    },
    "welcome_active": {
        "en": "⚙️ Currently active: <b>{active} of {total}</b> methods",
        "ru": "⚙️ Сейчас активно <b>{active} из {total}</b> методов обработки",
    },

    # ── Help ───────────────────────────────────────────────────────────────────
    "help_title": {
        "en": "📖 <b>Bot guide</b>",
        "ru": "📖 <b>Справка по боту</b>",
    },
    "help_body": {
        "en": (
            "\n\n<b>What the bot does:</b>\n"
            "Applies up to {total} invisible changes — color, audio, metadata, encoding — "
            "so the file gets a unique hash while looking and sounding identical to the original.\n\n"
            "<b>Formats:</b> MP4, MOV, AVI, MKV, WebM, FLV, WMV, MPEG, 3GP\n"
            "<b>Max size:</b> 2 GB\n"
            "<b>Upload:</b> file or direct link\n\n"
            "<b>Method categories:</b>\n"
            "📐 <b>Geometry</b> — flip, rotate, zoom, crop\n"
            "🎨 <b>Color</b> — brightness, contrast, hue, grading\n"
            "🔍 <b>Sharpness</b> — blur, sharpen, motion blur\n"
            "🌪 <b>Noise</b> — grain, chromatic aberration\n"
            "⏱ <b>Temporal</b> — FPS, speed, trim\n"
            "🔊 <b>Audio</b> — pitch, EQ, reverb, loudness\n"
            "💾 <b>Encoding</b> — codec, bitrate, metadata, GOP\n"
            "🖼 <b>Overlays</b> — invisible watermark, border, pixels\n"
            "⚡ <b>Advanced</b> — DCT, warp, steganography\n\n"
            "<b>Commands:</b>\n"
            "/settings — fine-tune each method\n"
            "/preset — choose a preset\n"
            "/status — current settings\n"
            "/cancel — cancel processing\n"
            "/language — change language\n"
            "/export, /import — save/load settings"
        ),
        "ru": (
            "\n\n<b>Что бот делает с видео:</b>\n"
            "Применяет до {total} незаметных изменений — цвет, звук, метаданные, кодирование — "
            "так, что файл получает уникальный хеш, но выглядит идентично оригиналу.\n\n"
            "<b>Форматы:</b> MP4, MOV, AVI, MKV, WebM, FLV, WMV, MPEG, 3GP\n"
            "<b>Максимальный размер:</b> 2 ГБ\n"
            "<b>Загрузка:</b> файлом или прямой ссылкой\n\n"
            "<b>Категории методов:</b>\n"
            "📐 <b>Геометрия</b> — отзеркаливание, поворот, зум, кроп\n"
            "🎨 <b>Цвет</b> — яркость, контраст, оттенок, цветокоррекция\n"
            "🔍 <b>Резкость</b> — размытие, шарп, motion blur\n"
            "🌪 <b>Шум</b> — зернистость, хроматическая аберрация\n"
            "⏱ <b>Время</b> — FPS, скорость, обрезка\n"
            "🔊 <b>Аудио</b> — тон, эквалайзер, реверб, нормализация\n"
            "💾 <b>Кодирование</b> — кодек, битрейт, метаданные, GOP\n"
            "🖼 <b>Наложения</b> — невидимый водяной знак, рамка, пиксели\n"
            "⚡ <b>Продвинутые</b> — DCT, деформации, стеганография\n\n"
            "<b>Команды:</b>\n"
            "/settings — тонкая настройка каждого метода\n"
            "/preset — выбор пресета\n"
            "/status — текущие настройки\n"
            "/cancel — отменить обработку\n"
            "/language — сменить язык\n"
            "/export, /import — сохранить/загрузить настройки"
        ),
    },

    # ── Status ─────────────────────────────────────────────────────────────────
    "status_title": {
        "en": "📊 <b>Current processing profile</b>\n",
        "ru": "📊 <b>Текущий профиль обработки</b>\n",
    },
    "status_uniq_on": {
        "en": "Uniqualization: <b>ON 🟢</b>",
        "ru": "Уникализация: <b>Включена 🟢</b>",
    },
    "status_uniq_off": {
        "en": "Uniqualization: <b>OFF 🔴</b>",
        "ru": "Уникализация: <b>Выключена 🔴</b>",
    },
    "status_active": {
        "en": "Active methods: <b>{active}/{total}</b>",
        "ru": "Активных методов: <b>{active}/{total}</b>",
    },
    "status_preset": {
        "en": "Preset: {emoji} <b>{label}</b>",
        "ru": "Текущий пресет: {emoji} <b>{label}</b>",
    },
    "status_processed": {
        "en": "\n📈 Videos processed: <b>{total}</b>",
        "ru": "\n📈 Обработано видео: <b>{total}</b>",
    },
    "btn_change_settings": {
        "en": "⚙️ Change settings",
        "ru": "⚙️ Изменить настройки",
    },
    "btn_change_preset": {
        "en": "🎨 Change preset",
        "ru": "🎨 Сменить пресет",
    },

    # ── Queue ──────────────────────────────────────────────────────────────────
    "queue_empty": {
        "en": "📭 No active jobs.\nTotal in queue: {pending}",
        "ru": "📭 Активных задач нет.\nВсего в очереди: {pending}",
    },
    "queue_job": {
        "en": "📋 <b>Your job</b>\n\nStatus: {status}\nTotal in queue: {pending}",
        "ru": "📋 <b>Ваша задача</b>\n\nСтатус: {status}\nВсего в очереди: {pending}",
    },
    "queue_pending": {"en": "⏳ Waiting", "ru": "⏳ В очереди"},
    "queue_processing": {"en": "⚙️ Processing — {pct}%", "ru": "⚙️ Обрабатывается — {pct}%"},
    "queue_done": {"en": "✅ Done", "ru": "✅ Завершено"},
    "queue_failed": {"en": "❌ Failed", "ru": "❌ Ошибка"},
    "queue_cancelled": {"en": "🚫 Cancelled", "ru": "🚫 Отменено"},
    "btn_cancel_job": {"en": "🚫 Cancel", "ru": "🚫 Отменить"},

    # ── Cancel ─────────────────────────────────────────────────────────────────
    "cancel_done": {"en": "🚫 Job cancelled.", "ru": "🚫 Задача отменена."},
    "cancel_none": {
        "en": "No pending jobs to cancel.",
        "ru": "Нет задач в ожидании для отмены.",
    },
    "cancel_impossible": {
        "en": "Can't stop already running job.",
        "ru": "Уже запущенную обработку остановить нельзя.",
    },

    # ── Stats ──────────────────────────────────────────────────────────────────
    "stats": {
        "en": "📈 <b>Statistics</b>\n\nTotal processed: <b>{total}</b> videos\nToday: <b>{today}</b> videos",
        "ru": "📈 <b>Статистика</b>\n\nВсего обработано: <b>{total}</b> видео\nСегодня: <b>{today}</b> видео",
    },

    # ── Export / Import ────────────────────────────────────────────────────────
    "export_caption": {
        "en": (
            "📤 <b>Settings exported</b>\n\n"
            "To restore on another device:\n"
            "send this file with caption <code>/import</code>"
        ),
        "ru": (
            "📤 <b>Настройки экспортированы</b>\n\n"
            "Чтобы восстановить на другом устройстве:\n"
            "отправьте этот файл с подписью <code>/import</code>"
        ),
    },
    "import_hint": {
        "en": (
            "📥 <b>Import settings</b>\n\n"
            "Now send the settings file (JSON).\n"
            "Just drag and drop — no caption needed."
        ),
        "ru": (
            "📥 <b>Импорт настроек</b>\n\n"
            "Теперь отправьте файл с настройками (JSON).\n"
            "Просто перетащите файл — подпись не нужна."
        ),
    },
    "import_ok": {
        "en": "✅ <b>Settings imported</b>\nActive methods: {active}/{total}",
        "ru": "✅ <b>Настройки импортированы</b>\nАктивных методов: {active}/{total}",
    },
    "import_err": {
        "en": "❌ Could not read settings from this file.\nMake sure it's a valid JSON exported via /export.",
        "ru": "❌ Не удалось прочитать настройки из этого файла.\nУбедитесь, что это JSON, экспортированный через /export.",
    },

    # ── Video card ─────────────────────────────────────────────────────────────
    "video_received": {
        "en": "📹 <b>Video received — ready to process</b>\n",
        "ru": "📹 <b>Видео получено — готово к обработке</b>\n",
    },
    "video_downloading": {
        "en": "📥 Downloading file ({size})…",
        "ru": "📥 Загружаю файл ({size})…",
    },
    "video_analysing": {
        "en": "🔍 Analysing video…",
        "ru": "🔍 Анализирую видео…",
    },
    "video_uniq_off": {
        "en": "⚠️ <b>Uniqualization is OFF</b>\nVideo will only be re-encoded.",
        "ru": "⚠️ <b>Уникализация выключена</b>\nВидео будет только перекодировано.",
    },
    "video_methods": {
        "en": "Methods: <b>{active}</b>  ·  {est} per copy",
        "ru": "Методов: <b>{active}</b>  ·  {est} на копию",
    },
    "video_batch": {
        "en": "\n📦 <b>{copies} copies</b>{var}  ·  total ~{total}",
        "ru": "\n📦 <b>{copies} копий</b>{var}  ·  итого ~{total}",
    },
    "video_active_cats": {
        "en": "<b>Active categories:</b>",
        "ru": "<b>Активные категории:</b>",
    },
    "video_copies_select": {
        "en": "👇 <b>Select number of copies:</b>",
        "ru": "👇 <b>Выбери количество копий:</b>",
    },
    "video_too_big": {
        "en": "❌ File too large. Max: <b>{mb} MB</b>.",
        "ru": "❌ Файл слишком большой. Максимум: <b>{mb} МБ</b>.",
    },
    "video_already_processing": {
        "en": "⏳ <b>Already processing</b>\nWait for it to finish or cancel.",
        "ru": "⏳ <b>Уже идёт обработка</b>\nДождитесь завершения или отмените.",
    },
    "video_rate_limit": {
        "en": "⏱ Wait <b>{sec} sec</b> before next request.",
        "ru": "⏱ Подождите <b>{sec} сек</b> перед следующим запросом.",
    },
    "btn_run": {"en": "▶️ Start processing", "ru": "▶️ Запустить обработку"},
    "btn_run_batch": {"en": "▶️ Run  ×{copies}{var}", "ru": "▶️ Запустить  ×{copies}{var}"},
    "btn_methods": {"en": "⚙️ Methods", "ru": "⚙️ Методы"},
    "btn_preset": {"en": "🎨 Preset", "ru": "🎨 Пресет"},
    "btn_cancel": {"en": "❌ Cancel", "ru": "❌ Отмена"},
    "btn_quick_methods": {"en": "⚡ Quick methods", "ru": "⚡ Быстрые методы"},
    "btn_back_card": {"en": "◀️ Back to card", "ru": "◀️ Назад к карточке"},
    "quick_methods_title": {
        "en": (
            "⚡ <b>Quick methods</b>\n\n"
            "Apply just one type of processing.\n"
            "Great for: <i>«make 100 copies → flip them all → 200 unique»</i>"
        ),
        "ru": (
            "⚡ <b>Быстрые методы</b>\n\n"
            "Применить только один тип обработки.\n"
            "Идеально для: <i>«100 копий → прогнать через зеркало → 200 уникальных»</i>"
        ),
    },
    "variation_none": {"en": "no variation", "ru": "без разброса"},
    "variation_val": {"en": "  |  variation ±{v}%", "ru": "  |  разброс ±{v}%"},

    # ── Queue in progress ──────────────────────────────────────────────────────
    "processing_title": {
        "en": "⚙️ <b>Processing {copies}…</b>\n",
        "ru": "⚙️ <b>Обрабатываю {copies}…</b>\n",
    },
    "copies_word_en": {
        "en": "{n} copy" if False else "",  # handled in code
        "ru": "",
    },
    "enqueued": {
        "en": "⏳ <b>Queued</b>\n\n░░░░░░░░░░░░░░░░░░░░  0%",
        "ru": "⏳ <b>Задача поставлена в очередь</b>\n\n░░░░░░░░░░░░░░░░░░░░  0%",
    },
    "sending_result": {
        "en": "📤 <b>Done! Sending file…</b>",
        "ru": "📤 <b>Готово! Отправляю файл…</b>",
    },
    "packing_zip": {
        "en": "📦 <b>Packing {n} files into archive…</b>",
        "ru": "📦 <b>Пакую {n} файлов в архив…</b>",
    },
    "copy_label": {"en": "Copy {i}/{n}", "ru": "Копия {i}/{n}"},
    "started": {"en": "▶️ Processing started!", "ru": "▶️ Обработка запущена!"},
    "started_batch": {
        "en": "▶️ Running! Making {n} unique copies",
        "ru": "▶️ Запущено! Делаю {n} уникальных копий",
    },
    "cancelled_upload": {"en": "🚫 Cancelled.", "ru": "🚫 Отменено."},
    "file_expired": {
        "en": "❌ File expired — send the video again.",
        "ru": "❌ Файл устарел — отправьте видео заново.",
    },

    # ── Result report ──────────────────────────────────────────────────────────
    "report_title": {"en": "✅ <b>Done! Video uniqualized</b>\n\n", "ru": "✅ <b>Готово! Видео уникализировано</b>\n\n"},
    "report_hash_ok": {
        "en": "✅ File is unique — hash differs from original",
        "ru": "✅ Файл уникален — хеш отличается от оригинала",
    },
    "report_hash_same": {
        "en": "⚠️ Hash matches original",
        "ru": "⚠️ Хеш совпадает с оригиналом",
    },
    "report_methods": {"en": "\n<b>Methods applied: {n}</b>\n", "ru": "\n<b>Применено методов: {n}</b>\n"},
    "report_size": {"en": "📦 Size: {in_sz} MB → {out_sz} MB ({diff} MB)\n", "ru": "📦 Размер: {in_sz} МБ → {out_sz} МБ ({diff} МБ)\n"},
    "report_time": {"en": "⏱ Time: {dur}\n", "ru": "⏱ Время: {dur}\n"},
    "report_seed": {"en": "🔑 Seed: <code>{seed}</code>\n\n", "ru": "🔑 Seed: <code>{seed}</code>\n\n"},
    "report_hashes": {"en": "<b>Hashes:</b>\n", "ru": "<b>Хеши:</b>\n"},
    "report_hash_before": {"en": "<code>Before: {h}…</code>\n", "ru": "<code>Было:  {h}…</code>\n"},
    "report_hash_after": {"en": "<code>After:  {h}…</code>", "ru": "<code>Стало: {h}…</code>"},
    "report_copy_label": {"en": "📦 <b>Copy {i}/{n}</b>\n{hash_note}", "ru": "📦 <b>Копия {i}/{n}</b>\n{hash_note}"},
    "report_zip_done": {
        "en": "✅ <b>Done! {n} copies</b>\n{hash_note}\nVariation: {var}",
        "ru": "✅ <b>Готово! {n} копий</b>\n{hash_note}\nРазброс: {var}",
    },
    "report_all_unique": {"en": "✅ All hashes unique", "ru": "✅ Все хеши уникальны"},
    "report_some_same": {"en": "⚠️ Some hashes matched", "ru": "⚠️ Часть хешей совпала"},
    "report_var_off": {"en": "off", "ru": "выкл"},

    # ── Settings ───────────────────────────────────────────────────────────────
    "settings_title": {
        "en": "⚙️ <b>Uniqualization settings</b>\n\nUniqualization: <b>{g_str}</b>\nActive methods: <b>{active}/{total}</b>\n\nSelect a category:",
        "ru": "⚙️ <b>Настройки уникализации</b>\n\nУникализация: <b>{g_str}</b>\nАктивных методов: <b>{active}/{total}</b>\n\nВыбери категорию:",
    },
    "settings_on": {"en": "ON 🟢", "ru": "включена 🟢"},
    "settings_off": {"en": "OFF 🔴", "ru": "выключена 🔴"},
    "btn_uniq_on": {"en": "🟢  Uniqualization ON  (tap to disable)", "ru": "🟢  Уникализация ВКЛЮЧЕНА  (нажми чтобы выкл)"},
    "btn_uniq_off": {"en": "🔴  Uniqualization OFF  (tap to enable)", "ru": "🔴  Уникализация ВЫКЛЮЧЕНА  (нажми чтобы вкл)"},
    "btn_presets": {"en": "🎨 Presets", "ru": "🎨 Пресеты"},
    "btn_export": {"en": "📤 Export", "ru": "📤 Экспорт"},
    "btn_close": {"en": "✖ Close", "ru": "✖ Закрыть"},
    "btn_back": {"en": "◀️ Back", "ru": "◀️ Назад"},
    "btn_all_on": {"en": "All ON ({en}/{tot})", "ru": "Вкл все ({en}/{tot})"},
    "btn_all_off": {"en": "All OFF ({en}/{tot})", "ru": "Выкл все ({en}/{tot})"},
    "cat_hint": {
        "en": "\n\nTap a method to see description and settings.\n✅ = on  |  ⬜ = off  |  [▁▂▄▆█] = intensity",
        "ru": "\n\nНажми на метод — увидишь описание и настройки.\n✅ = включён  |  ⬜ = выключен  |  [▁▂▄▆█] = интенсивность",
    },
    "method_on": {"en": "on", "ru": "включён"},
    "method_off": {"en": "off", "ru": "выключен"},
    "method_intensity": {"en": "\nIntensity: <b>{label}</b>  <code>{bar}</code>", "ru": "\nИнтенсивность: <b>{label}</b>  <code>{bar}</code>"},
    "method_freq": {"en": "\nFrequency: <b>{freq}%</b>  <i>(chance to apply per video)</i>", "ru": "\nЧастота: <b>{freq}%</b>  <i>(вероятность применения к каждому видео)</i>"},
    "method_freq_always": {"en": "\nFrequency: <b>Always</b>  <i>(applies to every video)</i>", "ru": "\nЧастота: <b>Всегда</b>  <i>(применяется к каждому видео)</i>"},
    "toggled_on": {"en": "✅ Enabled", "ru": "✅ Включён"},
    "toggled_off": {"en": "⬜ Disabled", "ru": "⬜ Выключен"},
    "all_enabled": {"en": "All enabled", "ru": "Все включены"},
    "all_disabled": {"en": "All disabled", "ru": "Все выключены"},
    "intensity_set": {"en": "Intensity: {label}", "ru": "Интенсивность: {label}"},
    "intensity_type": {"en": "Type a number 1-100 in chat:", "ru": "Введите число от 1 до 100 в чат:"},
    "frequency_set": {"en": "Frequency: {freq}%", "ru": "Частота: {freq}%"},
    "exported": {"en": "📤 Settings exported.", "ru": "📤 Настройки экспортированы."},

    # ── Presets ────────────────────────────────────────────────────────────────
    "presets_title": {"en": "🎨 <b>Presets & templates</b>\n\n", "ru": "🎨 <b>Пресеты и шаблоны уникализации</b>\n\n"},
    "presets_levels": {"en": "<b>Uniqualization levels:</b>", "ru": "<b>Уровни уникализации:</b>"},
    "presets_templates": {"en": "\n<b>Specialized templates:</b>", "ru": "\n<b>Специализированные шаблоны:</b>"},
    "presets_mine": {"en": "─── My presets ───", "ru": "─── Мои пресеты ───"},
    "btn_save_preset": {"en": "💾 Save current settings as preset", "ru": "💾 Сохранить текущие настройки как пресет"},
    "btn_back_settings": {"en": "◀️ Back to settings", "ru": "◀️ К настройкам"},
    "preset_applied": {"en": "{emoji} Preset «{label}» applied! Active: {active}", "ru": "{emoji} Пресет «{label}» применён! Активных: {active}"},
    "template_applied": {"en": "{emoji} Template «{name}» applied! Active: {active}", "ru": "{emoji} Шаблон «{name}» применён! Активных: {active}"},
    "preset_not_found": {"en": "❌ Preset not found.", "ru": "❌ Пресет не найден."},
    "preset_deleted": {"en": "🗑 Preset «{name}» deleted.", "ru": "🗑 Пресет «{name}» удалён."},
    "preset_save_prompt": {
        "en": "💾 <b>Save preset</b>\n\nEnter a name for this preset (up to 20 chars):",
        "ru": "💾 <b>Сохранение пресета</b>\n\nВведите название для пресета (до 20 символов):",
    },
    "preset_saved": {
        "en": "✅ Preset «<b>{name}</b>» saved! ({active} methods)",
        "ru": "✅ Пресет «<b>{name}</b>» сохранён! ({active} методов)",
    },
    "preset_name_empty": {
        "en": "❌ Name cannot be empty.",
        "ru": "❌ Название не может быть пустым.",
    },
    "preset_unknown": {
        "en": "❌ Unknown preset.",
        "ru": "❌ Неизвестный пресет.",
    },
    "template_not_found": {
        "en": "❌ Template not found.",
        "ru": "❌ Шаблон не найден.",
    },
    "preset_applied_inline": {
        "en": "\n\n{emoji} Applied: <b>{label}</b> ({active} methods)",
        "ru": "\n\n{emoji} Применён: <b>{label}</b> ({active} методов)",
    },
    "template_applied_inline": {
        "en": "\n\n{emoji} Applied template: <b>{name}</b>\n<i>{desc}</i>\nActive methods: {active}",
        "ru": "\n\n{emoji} Применён шаблон: <b>{name}</b>\n<i>{desc}</i>\nАктивных методов: {active}",
    },
    "btn_delete_preset": {"en": "🗑 delete", "ru": "🗑 удалить"},
    "hdr_levels": {"en": "── Uniqualization levels ──", "ru": "── Уровни уникализации ──"},
    "hdr_templates": {"en": "── Specialized templates ──", "ru": "── Специализированные шаблоны ──"},
    "hdr_my_presets": {"en": "── My presets ──", "ru": "── Мои пресеты ──"},

    # Preset names
    "preset_light":      {"en": "Light",      "ru": "Лёгкая"},
    "preset_medium":     {"en": "Medium",     "ru": "Средняя"},
    "preset_iphone":     {"en": "iPhone",     "ru": "iPhone"},
    "preset_aggressive": {"en": "Aggressive", "ru": "Агрессивная"},
    "preset_maximum":    {"en": "Maximum",    "ru": "Максимальная"},

    # Preset descriptions
    "preset_light_desc":      {"en": "~11 methods — invisible to eye",         "ru": "~11 методов — незаметно глазу"},
    "preset_medium_desc":     {"en": "~19 methods — optimal balance",          "ru": "~19 методов — оптимальный баланс"},
    "preset_iphone_desc":     {"en": "~15 methods — like iPhone processing ⭐", "ru": "~15 методов — как обработка на айфоне ⭐"},
    "preset_aggressive_desc": {"en": "~38 methods — maximum uniqueness",       "ru": "~38 методов — максимальная уникальность"},
    "preset_maximum_desc":    {"en": "all 70 methods — full processing",       "ru": "все 70 методов — полная обработка"},

    # Template names
    "tpl_codec_name":          {"en": "Encoding only",             "ru": "Только кодирование"},
    "tpl_visual_name":         {"en": "Visual only",               "ru": "Только визуал"},
    "tpl_audio_name":          {"en": "Audio only",                "ru": "Только аудио"},
    "tpl_meta_name":           {"en": "Metadata only",             "ru": "Только метаданные"},
    "tpl_soft_name":           {"en": "Soft (no artifacts)",       "ru": "Мягкая (без артефактов)"},
    "tpl_full_noaudio_name":   {"en": "Visual + codec (no audio)", "ru": "Визуал + кодек (без аудио)"},

    # Template descriptions
    "tpl_codec_desc":        {"en": "Changes codec, bitrate and metadata — no picture/sound changes.\nFile looks identical but has a different hash.", "ru": "Меняет кодек, битрейт и метаданные — без изменения картинки и звука.\nФайл визуально идентичен, но имеет другой хеш."},
    "tpl_visual_desc":       {"en": "Color, geometry, sharpness, noise — no audio or codec changes.\nAudio track stays untouched.", "ru": "Цвет, геометрия, резкость, шум — без изменения звука и кодека.\nАудиодорожка остаётся нетронутой."},
    "tpl_audio_desc":        {"en": "Changes only the audio track: pitch, EQ, loudness.\nVideo track is not touched.", "ru": "Меняет только звуковую дорожку: тон, эквалайзер, громкость.\nВидеодорожка не трогается."},
    "tpl_meta_desc":         {"en": "Clears original metadata and fills with random values.\nFastest way to change the hash.", "ru": "Очищает оригинальные метаданные и заполняет случайными.\nСамый быстрый способ изменить хеш."},
    "tpl_soft_desc":         {"en": "Only invisible changes: metadata, encoding, audio normalization.\nQuality is 100% preserved.", "ru": "Только незаметные изменения: метаданные, кодирование, нормализация звука.\nКачество на 100% сохраняется."},
    "tpl_full_noaudio_desc": {"en": "All visual methods + encoding, but audio is not touched.", "ru": "Все визуальные методы + кодирование, но аудио не трогается."},

    # Custom copies
    "custom_copies_prompt": {
        "en": "✏️ Enter number of copies (1–999):",
        "ru": "✏️ Введите количество копий (1–999):",
    },
    "custom_copies_invalid": {
        "en": "❌ Enter a number from 1 to 999.",
        "ru": "❌ Введите число от 1 до 999.",
    },

    # Worker progress messages
    "worker_processing": {
        "en": "⚙️ <b>Processing {copies}…</b>\n",
        "ru": "⚙️ <b>Обрабатываю {copies}…</b>\n",
    },
    "worker_copies_word": {
        "en": "{n} copy",
        "ru": "{n} копию",
    },
    "worker_copies_word_plural": {
        "en": "{n} copies",
        "ru": "{n} копий",
    },
    "worker_waiting":   {"en": "⬜ waiting", "ru": "⬜ ожидает"},
    "worker_starting":  {"en": "⚙️ starting…", "ru": "⚙️ запускается…"},
    "worker_empty":     {"en": "⚠️ empty file", "ru": "⚠️ пустой файл"},
    "worker_done":      {"en": "✅ done  <code>{h}…</code>", "ru": "✅ готово  <code>{h}…</code>"},
    "worker_error":     {"en": "❌ error", "ru": "❌ ошибка"},
    "worker_copy_of":   {"en": "Copy {i}/{n}", "ru": "Копия {i}/{n}"},
    "worker_hash_ok":   {"en": "✅ Hash is unique", "ru": "✅ Хеш уникален"},
    "worker_hash_same": {"en": "⚠️ Hash matched", "ru": "⚠️ Хеш совпал"},
    "worker_sending":   {"en": "📦 <b>Sending {n} files…</b>", "ru": "📦 <b>Отправляю {n} файлов…</b>"},
    "worker_all_unique": {"en": "✅ All hashes unique", "ru": "✅ Все хеши уникальны"},
    "worker_some_same":  {"en": "⚠️ Some hashes matched", "ru": "⚠️ Часть хешей совпала"},
    "worker_var_off":    {"en": "off", "ru": "выкл"},
    "worker_zip_done": {
        "en": "✅ <b>Done! {n} copies</b>{part}\n{hash_note}\nVariation: {var}",
        "ru": "✅ <b>Готово! {n} копий</b>{part}\n{hash_note}\nРазброс параметров: {var}",
    },
    "worker_part_label": {"en": " (part {i}/{n})", "ru": " (часть {i}/{n})"},
    "worker_too_big": {
        "en": "⚠️ Copy {i} is too large ({size} MB > {limit} MB limit).\nFile processed but cannot be sent.",
        "ru": "⚠️ Копия {i} слишком большая ({size} МБ > {limit} МБ лимит).\nФайл обработан, но не может быть отправлен.",
    },
    "worker_send_failed": {
        "en": "⚠️ <b>Processing complete, but some files could not be sent</b>\nProcessed: {done}/{total}\nFiles exceed size limit or network error.\nTry fewer copies.",
        "ru": "⚠️ <b>Обработка завершена, но не все файлы удалось отправить</b>\nОбработано: {done}/{total}\nФайл(ы) превышают лимит или ошибка сети.\nПопробуйте уменьшить количество копий.",
    },

    # ── Stage labels ───────────────────────────────────────────────────────────
    "stage_analyse":  {"en": "<i>🔍 Analysing video…</i>", "ru": "<i>🔍 Анализирую видео…</i>"},
    "stage_plan":     {"en": "<i>📋 Building processing plan…</i>", "ru": "<i>📋 Составляю план обработки…</i>"},
    "stage_process":  {"en": "<i>⚙️ Applying methods…</i>", "ru": "<i>⚙️ Применяю методы уникализации…</i>"},
    "stage_final":    {"en": "<i>🔬 Final pass…</i>", "ru": "<i>🔬 Финальная обработка…</i>"},
    "stage_done":     {"en": "<i>✅ Finishing…</i>", "ru": "<i>✅ Завершаю…</i>"},

    # ── Errors ─────────────────────────────────────────────────────────────────
    "err_download":    {"en": "❌ Download error: {e}", "ru": "❌ Ошибка загрузки: {e}"},
    "err_analyse":     {"en": "❌ Could not read video:\n{e}", "ru": "❌ Не удалось прочитать видео:\n{e}"},
    "err_processing":  {"en": "❌ <b>Processing error:</b>\n{e}", "ru": "❌ <b>Ошибка обработки:</b>\n{e}"},
    "err_unexpected":  {"en": "❌ <b>Unexpected error:</b>\n{e}", "ru": "❌ <b>Неожиданная ошибка:</b>\n{e}"},
    "err_cancel_impossible": {
        "en": "Job already running — can't cancel.",
        "ru": "Задача уже обрабатывается — не отменить.",
    },
}


def t(key: str, lang: str, **kwargs) -> str:
    """Get translated string. Falls back to English."""
    bucket = _STRINGS.get(key, {})
    text   = bucket.get(lang) or bucket.get("en", f"[{key}]")
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text
