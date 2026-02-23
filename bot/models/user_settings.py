"""
User settings model.  Stored as JSON in data/users/<user_id>.json
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Optional

from bot.config import USERS_DIR


# ── Intensity helpers ─────────────────────────────────────────────────────────
_OLD_TO_NEW = {1: 1, 2: 25, 3: 50, 4: 75, 5: 100}  # migrate old 1-5 → 1-100

def intensity_bar(pct: int) -> str:
    """Visual bar for intensity percentage."""
    filled = max(0, min(10, round(pct / 10)))
    return "▰" * filled + "▱" * (10 - filled)


@dataclass
class MethodSettings:
    enabled:   bool = True
    intensity: int  = 50      # 1–100 %
    frequency: int  = 50      # 0–100 %


@dataclass
class UserSettings:
    user_id:        int
    global_enabled: bool = True
    language:       str  = "en"   # "en" | "ru"
    # method_id (1-70) → MethodSettings
    methods: Dict[int, MethodSettings] = field(default_factory=dict)
    # preset_name → {method_id: {enabled, intensity, frequency}}
    custom_presets: Dict[str, dict] = field(default_factory=dict)
    # stats
    processed_total: int = 0
    processed_today:  int = 0

    # ── persistence ───────────────────────────────────────────────────────────

    @staticmethod
    def _path(user_id: int) -> Path:
        return USERS_DIR / f"{user_id}.json"

    def save(self) -> None:
        d = {
            "user_id":        self.user_id,
            "global_enabled": self.global_enabled,
            "language":       self.language,
            "methods": {
                str(mid): asdict(ms)
                for mid, ms in self.methods.items()
            },
            "custom_presets":  self.custom_presets,
            "processed_total": self.processed_total,
            "processed_today": self.processed_today,
        }
        self._path(self.user_id).write_text(
            json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @classmethod
    def load(cls, user_id: int) -> "UserSettings":
        p = cls._path(user_id)
        if not p.exists():
            return cls.default(user_id)
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            methods = {
                int(mid): MethodSettings(**ms)
                for mid, ms in d.get("methods", {}).items()
            }
            obj = cls(
                user_id=user_id,
                global_enabled=d.get("global_enabled", True),
                language=d.get("language", "en"),
                methods=methods,
                custom_presets=d.get("custom_presets", {}),
                processed_total=d.get("processed_total", 0),
                processed_today=d.get("processed_today", 0),
            )
            # fill in any missing methods with defaults
            obj._ensure_all_methods()
            # migrate old 1-5 intensity scale to 1-100
            for ms in obj.methods.values():
                if ms.intensity <= 5:
                    ms.intensity = _OLD_TO_NEW.get(ms.intensity, ms.intensity)
            return obj
        except Exception:
            return cls.default(user_id)

    @classmethod
    def default(cls, user_id: int) -> "UserSettings":
        obj = cls(user_id=user_id)
        obj._ensure_all_methods()
        return obj

    def _ensure_all_methods(self) -> None:
        from bot.processors.methods import ALL_METHODS
        for m in ALL_METHODS:
            if m.id not in self.methods:
                self.methods[m.id] = MethodSettings(
                    enabled=m.default_enabled,
                    intensity=m.default_intensity,
                    frequency=m.default_frequency,
                )

    # ── helpers ───────────────────────────────────────────────────────────────

    def get_method(self, method_id: int) -> MethodSettings:
        return self.methods[method_id]

    def toggle_method(self, method_id: int) -> bool:
        ms = self.methods[method_id]
        ms.enabled = not ms.enabled
        return ms.enabled

    def set_intensity(self, method_id: int, value: int) -> None:
        self.methods[method_id].intensity = max(1, min(100, value))

    def set_frequency(self, method_id: int, value: int) -> None:
        self.methods[method_id].frequency = max(0, min(100, value))

    def toggle_category(self, cat_id: int) -> bool:
        from bot.processors.methods import get_methods_by_category
        methods = get_methods_by_category(cat_id)
        any_on = any(self.methods[m.id].enabled for m in methods)
        new_state = not any_on
        for m in methods:
            self.methods[m.id].enabled = new_state
        return new_state

    def category_enabled_count(self, cat_id: int) -> tuple[int, int]:
        """Returns (enabled_count, total_count)."""
        from bot.processors.methods import get_methods_by_category
        methods = get_methods_by_category(cat_id)
        enabled = sum(1 for m in methods if self.methods[m.id].enabled)
        return enabled, len(methods)

    # ── active methods for processing ─────────────────────────────────────────

    def get_active_methods(self) -> list[tuple]:
        """
        Returns list of (method, MethodSettings) for methods that should
        be applied to this video, based on enabled + frequency roll.
        Geometry methods (category 1) always apply when enabled (no frequency roll).
        """
        if not self.global_enabled:
            return []
        from bot.processors.methods import ALL_METHODS
        active = []
        for m in ALL_METHODS:
            ms = self.methods.get(m.id)
            if not ms or not ms.enabled:
                continue
            # Geometry methods (cat 1) always apply when enabled
            if m.category == 1 or random.randint(1, 100) <= ms.frequency:
                active.append((m, ms))
        return active

    # ── preset management ─────────────────────────────────────────────────────

    def apply_preset(self, preset_name: str) -> None:
        from bot.processors.methods import PRESETS
        if preset_name in PRESETS:
            cfg = PRESETS[preset_name]
        elif preset_name in self.custom_presets:
            cfg = self.custom_presets[preset_name]
        else:
            return
        for mid_str, vals in cfg.items():
            mid = int(mid_str)
            if mid in self.methods:
                self.methods[mid].enabled   = vals.get("enabled",   self.methods[mid].enabled)
                self.methods[mid].intensity = vals.get("intensity",  self.methods[mid].intensity)
                self.methods[mid].frequency = vals.get("frequency",  self.methods[mid].frequency)

    def save_custom_preset(self, name: str) -> None:
        self.custom_presets[name] = {
            str(mid): {
                "enabled":   ms.enabled,
                "intensity": ms.intensity,
                "frequency": ms.frequency,
            }
            for mid, ms in self.methods.items()
        }
        self.save()

    def delete_custom_preset(self, name: str) -> None:
        self.custom_presets.pop(name, None)
        self.save()

    # ── import / export ───────────────────────────────────────────────────────

    def export_json(self) -> str:
        return json.dumps({
            "global_enabled": self.global_enabled,
            "methods": {
                str(mid): asdict(ms)
                for mid, ms in self.methods.items()
            },
        }, ensure_ascii=False, indent=2)

    def import_json(self, raw: str) -> bool:
        try:
            d = json.loads(raw)
            if "global_enabled" in d:
                self.global_enabled = bool(d["global_enabled"])
            if "methods" in d:
                for mid_str, vals in d["methods"].items():
                    mid = int(mid_str)
                    if mid in self.methods:
                        ms = self.methods[mid]
                        ms.enabled   = bool(vals.get("enabled",   ms.enabled))
                        ms.intensity = int(vals.get("intensity",  ms.intensity))
                        ms.frequency = int(vals.get("frequency",  ms.frequency))
            self.save()
            return True
        except Exception:
            return False
