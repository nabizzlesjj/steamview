"""SteamView -- Decky plugin backend.

This file is deliberately thin. It owns the decky lifecycle and the RPC
surface the frontend calls through ``@decky/api``'s ``call``; all the
actual logic lives in ``py_modules/steamview`` where it can be unit
tested off-device without a Steam Deck or a network.

Every method returns a well-formed result even on failure. Nothing here
may raise into the UI -- a broken media preview must never be able to
break the Steam library.
"""

import os
import sys

import decky

# The plugin's own modules ship in py_modules/, which decky puts on the
# path for us; the explicit insert keeps direct execution working too.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "py_modules"))

from steamview import compat  # noqa: E402
from steamview.cache import MediaCache  # noqa: E402
from steamview.resolver import MediaResolver  # noqa: E402
from steamview.settings import SettingsStore  # noqa: E402

CACHE_SUBDIR = "media-cache"


class Plugin:
    async def _main(self):
        self.settings = SettingsStore(compat.settings_dir())
        self.settings.load()
        self.cache = MediaCache(os.path.join(compat.runtime_dir(), CACHE_SUBDIR))
        self.resolver = MediaResolver(self.cache)
        decky.logger.info("SteamView backend ready (cache: %s)", self.cache.directory)

    async def _unload(self):
        decky.logger.info("SteamView backend unloading")

    async def _uninstall(self):
        try:
            removed = self.cache.clear()
            decky.logger.info("SteamView removed %d cached media entries", removed)
        except Exception as exc:  # noqa: BLE001
            decky.logger.warning("SteamView uninstall cleanup failed: %s", exc)

    # ------------------------------------------------------------------
    # Media
    # ------------------------------------------------------------------

    async def get_media_for(self, entry=None):
        """Resolve media for one library entry.

        Returns the media object described in ARCHITECTURE.md, or a well-formed
        empty one. Never raises.
        """
        try:
            data_saver = bool(self.settings.get().get("data_saver"))
            return await self.resolver.get_media(entry, data_saver=data_saver)
        except Exception as exc:  # noqa: BLE001
            decky.logger.warning("get_media_for failed: %s", exc)
            return {
                "key": "",
                "kind": "",
                "title": "",
                "source": "empty",
                "resolved_appid": None,
                "trailer_url": None,
                "trailer_kind": None,
                "trailer_thumbnail": None,
                "screenshot_urls": [],
                "hero_url": None,
                "note": "backend-error",
            }

    async def prefetch(self, entries=None):
        """Warm the cache for entries near the focused one. Best effort."""
        try:
            data_saver = bool(self.settings.get().get("data_saver"))
            return await self.resolver.prefetch(entries, data_saver=data_saver)
        except Exception as exc:  # noqa: BLE001
            decky.logger.debug("prefetch failed: %s", exc)
            return 0

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    async def clear_cache(self):
        try:
            removed = self.resolver.clear_cache()
            decky.logger.info("SteamView cleared %d cached media entries", removed)
            return {"ok": True, "removed": removed}
        except Exception as exc:  # noqa: BLE001
            decky.logger.warning("clear_cache failed: %s", exc)
            return {"ok": False, "removed": 0}

    async def cache_stats(self):
        try:
            return self.cache.stats()
        except Exception as exc:  # noqa: BLE001
            decky.logger.debug("cache_stats failed: %s", exc)
            return {"directory": "", "entries": 0, "memory_entries": 0, "bytes": 0}

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    async def get_settings(self):
        try:
            return self.settings.get()
        except Exception as exc:  # noqa: BLE001
            decky.logger.warning("get_settings failed: %s", exc)
            from steamview.settings import validate

            return validate(None)

    async def set_settings(self, patch=None):
        try:
            return self.settings.update(patch)
        except Exception as exc:  # noqa: BLE001
            decky.logger.warning("set_settings failed: %s", exc)
            return await self.get_settings()

    async def reset_settings(self):
        try:
            return self.settings.reset()
        except Exception as exc:  # noqa: BLE001
            decky.logger.warning("reset_settings failed: %s", exc)
            return await self.get_settings()
