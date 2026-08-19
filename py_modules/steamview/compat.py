"""Runtime glue between the plugin backend and the decky loader.

Everything in this module has a standard-library fallback so the rest of
the backend imports cleanly under pytest, where the ``decky`` module that
the loader injects does not exist.
"""

from __future__ import annotations

import logging
import os
import tempfile

try:  # pragma: no cover - only true on-device
    import decky  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - the test/CI path
    decky = None  # type: ignore[assignment]


def get_logger() -> logging.Logger:
    """The plugin logger, or a plain stdlib one when running off-device."""
    if decky is not None and getattr(decky, "logger", None) is not None:
        return decky.logger  # type: ignore[no-any-return]
    logger = logging.getLogger("steamview")
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


def _dir_from_decky(attr: str, fallback_suffix: str) -> str:
    """Resolve a decky-provided directory, falling back to a temp dir."""
    path = getattr(decky, attr, None) if decky is not None else None
    if not path:
        path = os.path.join(tempfile.gettempdir(), "steamview", fallback_suffix)
    os.makedirs(path, exist_ok=True)
    return str(path)


def runtime_dir() -> str:
    """Where on-disk caches live."""
    return _dir_from_decky("DECKY_PLUGIN_RUNTIME_DIR", "runtime")


def settings_dir() -> str:
    """Where the settings JSON lives."""
    return _dir_from_decky("DECKY_PLUGIN_SETTINGS_DIR", "settings")


logger = get_logger()
