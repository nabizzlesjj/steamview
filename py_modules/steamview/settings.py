"""Persisted plugin settings with validation and sane fallbacks.

Every value is validated on load. A settings file that has been
hand-edited, truncated, or written by an older version of the plugin must
never produce a broken UI -- unknown keys are dropped and out-of-range
values are clamped back to something usable.
"""

from __future__ import annotations

import json
import os
from typing import Any

from .compat import logger

PREVIEW_MODES = ("trailer", "screenshots", "off")
POSITIONS = ("top-left", "top-right", "bottom-left", "bottom-right")
SIZES = ("s", "m", "l")

AUTOPLAY_DELAY_MIN = 0
AUTOPLAY_DELAY_MAX = 5000

DEFAULTS: dict[str, Any] = {
    "enabled": True,
    "preview_mode": "trailer",
    "autoplay_delay_ms": 600,
    "muted": True,
    "loop": True,
    "position": "bottom-right",
    "size": "m",
    "data_saver": False,
}

SETTINGS_FILENAME = "settings.json"


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "1", "yes", "on"):
            return True
        if lowered in ("false", "0", "no", "off"):
            return False
    return default


def _as_choice(value: Any, choices: tuple[str, ...], default: str) -> str:
    if isinstance(value, str) and value.strip().lower() in choices:
        return value.strip().lower()
    return default


def _as_int(value: Any, low: int, high: int, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def validate(raw: Any) -> dict[str, Any]:
    """Coerce ``raw`` into a complete, in-range settings dict."""
    source = raw if isinstance(raw, dict) else {}
    return {
        "enabled": _as_bool(source.get("enabled"), DEFAULTS["enabled"]),
        "preview_mode": _as_choice(source.get("preview_mode"), PREVIEW_MODES, DEFAULTS["preview_mode"]),
        "autoplay_delay_ms": _as_int(
            source.get("autoplay_delay_ms"),
            AUTOPLAY_DELAY_MIN,
            AUTOPLAY_DELAY_MAX,
            DEFAULTS["autoplay_delay_ms"],
        ),
        "muted": _as_bool(source.get("muted"), DEFAULTS["muted"]),
        "loop": _as_bool(source.get("loop"), DEFAULTS["loop"]),
        "position": _as_choice(source.get("position"), POSITIONS, DEFAULTS["position"]),
        "size": _as_choice(source.get("size"), SIZES, DEFAULTS["size"]),
        "data_saver": _as_bool(source.get("data_saver"), DEFAULTS["data_saver"]),
    }


class SettingsStore:
    """Reads and writes ``settings.json`` in the plugin's settings dir."""

    def __init__(self, directory: str, filename: str = SETTINGS_FILENAME) -> None:
        self.path = os.path.join(directory, filename)
        self._values = validate(None)
        self._loaded = False

    def load(self) -> dict[str, Any]:
        """Read from disk, validating. Missing or corrupt file -> defaults."""
        raw: Any = None
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as exc:
            logger.warning("steamview.settings: %s unreadable, using defaults: %s", self.path, exc)
        self._values = validate(raw)
        self._loaded = True
        return dict(self._values)

    def get(self) -> dict[str, Any]:
        if not self._loaded:
            return self.load()
        return dict(self._values)

    def update(self, patch: Any) -> dict[str, Any]:
        """Merge ``patch`` over the current values, validate, persist."""
        current = self.get()
        if isinstance(patch, dict):
            current.update(patch)
        self._values = validate(current)
        self._save()
        return dict(self._values)

    def reset(self) -> dict[str, Any]:
        self._values = validate(None)
        self._save()
        return dict(self._values)

    def _save(self) -> None:
        temporary = self.path + ".tmp"
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump(self._values, handle, indent=2)
            os.replace(temporary, self.path)
        except (OSError, TypeError, ValueError) as exc:
            logger.warning("steamview.settings: failed to persist %s: %s", self.path, exc)
            try:
                os.unlink(temporary)
            except OSError:
                pass
