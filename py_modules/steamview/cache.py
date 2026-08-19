"""Two-layer TTL cache: in-memory for the current session, JSON on disk.

Scrolling a library re-visits the same handful of games constantly, and
the disk layer means a game resolved yesterday costs zero requests today.

Failures are cached too, on a much shorter TTL. Without that, every pass
over a game with no store entry would re-hit the network.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Callable

from .compat import logger

#: Successful resolutions change rarely -- a game's trailer is stable.
DEFAULT_TTL = 7 * 24 * 60 * 60

#: Failures might be transient (offline, rate limited), so retry sooner.
DEFAULT_NEGATIVE_TTL = 60 * 60

#: Disk entries beyond this are pruned oldest-first.
DEFAULT_MAX_ENTRIES = 600

_ENTRY_SUFFIX = ".json"


def _filename(key: str) -> str:
    return hashlib.sha1(key.encode("utf-8")).hexdigest() + _ENTRY_SUFFIX


class MediaCache:
    """Cache of resolved media objects, keyed by :attr:`LibraryEntry.cache_key`."""

    def __init__(
        self,
        directory: str,
        ttl: float = DEFAULT_TTL,
        negative_ttl: float = DEFAULT_NEGATIVE_TTL,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.directory = directory
        self.ttl = ttl
        self.negative_ttl = negative_ttl
        self.max_entries = max_entries
        self._clock = clock
        self._memory: dict[str, tuple[float, dict[str, Any]]] = {}
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        try:
            os.makedirs(self.directory, exist_ok=True)
        except OSError as exc:  # pragma: no cover - unwritable runtime dir
            logger.warning("steamview.cache: cannot create %s: %s", self.directory, exc)

    def _path(self, key: str) -> str:
        return os.path.join(self.directory, _filename(key))

    def get(self, key: str) -> dict[str, Any] | None:
        """The cached value for ``key``, or ``None`` if missing or stale."""
        now = self._clock()

        cached = self._memory.get(key)
        if cached is not None:
            expires_at, value = cached
            if expires_at > now:
                return value
            self._memory.pop(key, None)

        path = self._path(key)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                record = json.load(handle)
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as exc:
            logger.debug("steamview.cache: discarding unreadable entry %s: %s", path, exc)
            self._unlink(path)
            return None

        if not isinstance(record, dict):
            self._unlink(path)
            return None

        expires_at = record.get("expires_at")
        value = record.get("value")
        if not isinstance(expires_at, (int, float)) or not isinstance(value, dict):
            self._unlink(path)
            return None
        if expires_at <= now:
            self._unlink(path)
            return None

        self._memory[key] = (float(expires_at), value)
        return value

    def put(self, key: str, value: dict[str, Any], ttl: float | None = None) -> None:
        """Store ``value`` under ``key``."""
        if not isinstance(value, dict):
            return
        effective_ttl = self.ttl if ttl is None else ttl
        if effective_ttl <= 0:
            return
        expires_at = self._clock() + effective_ttl
        self._memory[key] = (expires_at, value)

        record = {"key": key, "expires_at": expires_at, "value": value}
        path = self._path(key)
        temporary = path + ".tmp"
        try:
            self._ensure_dir()
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump(record, handle)
            os.replace(temporary, path)
        except (OSError, TypeError, ValueError) as exc:
            logger.warning("steamview.cache: failed to write %s: %s", path, exc)
            self._unlink(temporary)
            return
        self.prune()

    def put_failure(self, key: str, value: dict[str, Any]) -> None:
        """Store an empty/failed resolution on the short negative TTL."""
        self.put(key, value, ttl=self.negative_ttl)

    def invalidate(self, key: str) -> None:
        self._memory.pop(key, None)
        self._unlink(self._path(key))

    def clear(self) -> int:
        """Drop every entry. Returns how many disk entries were removed."""
        self._memory.clear()
        removed = 0
        try:
            names = os.listdir(self.directory)
        except OSError:
            return 0
        for name in names:
            if not name.endswith(_ENTRY_SUFFIX):
                continue
            if self._unlink(os.path.join(self.directory, name)):
                removed += 1
        return removed

    def prune(self) -> int:
        """Evict the oldest disk entries past :attr:`max_entries`."""
        if self.max_entries <= 0:
            return 0
        try:
            names = [n for n in os.listdir(self.directory) if n.endswith(_ENTRY_SUFFIX)]
        except OSError:
            return 0
        if len(names) <= self.max_entries:
            return 0

        stamped: list[tuple[float, str]] = []
        for name in names:
            path = os.path.join(self.directory, name)
            try:
                stamped.append((os.path.getmtime(path), path))
            except OSError:
                continue
        stamped.sort()

        removed = 0
        for _, path in stamped[: max(0, len(stamped) - self.max_entries)]:
            if self._unlink(path):
                removed += 1
        if removed:
            logger.debug("steamview.cache: pruned %d entries", removed)
        return removed

    def stats(self) -> dict[str, Any]:
        try:
            names = [n for n in os.listdir(self.directory) if n.endswith(_ENTRY_SUFFIX)]
        except OSError:
            names = []
        total_bytes = 0
        for name in names:
            try:
                total_bytes += os.path.getsize(os.path.join(self.directory, name))
            except OSError:
                continue
        return {
            "directory": self.directory,
            "entries": len(names),
            "memory_entries": len(self._memory),
            "bytes": total_bytes,
        }

    @staticmethod
    def _unlink(path: str) -> bool:
        try:
            os.unlink(path)
            return True
        except FileNotFoundError:
            return False
        except OSError as exc:  # pragma: no cover - permissions
            logger.debug("steamview.cache: cannot remove %s: %s", path, exc)
            return False
