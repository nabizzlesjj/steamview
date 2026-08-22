"""Media resolution: the two paths described in DESIGN.md, plus caching.

**Path A -- native Steam game.** The appid is real, so ``appdetails``
gives us movies and screenshots directly.

**Path B -- non-Steam shortcut.** There is no store appid, only a display
name. Resolve that name to an appid via ``storesearch`` and run Path A;
most multi-store titles are also on Steam, so this recovers a real
trailer. When no candidate clears the confidence threshold, fall back to
the artwork the client already has for the shortcut.

Every public method is exception-safe. A resolution that fails for any
reason returns a well-formed, empty :class:`MediaResult` -- the overlay
then shows hero art or hides itself, and the library is untouched.
"""

from __future__ import annotations

import asyncio
from typing import Any, Iterable

from . import matching, media, steamstore
from .cache import MediaCache
from .compat import logger
from .entries import ENTRY_KIND_STEAM, LibraryEntry, parse_entry
from .http import url_exists

#: Ceiling on simultaneous outbound requests, so a fast scroll or a
#: prefetch burst cannot saturate the Deck's connection.
DEFAULT_MAX_CONCURRENCY = 3

#: Neighbours warmed per prefetch call. Beyond this the user has almost
#: certainly changed direction anyway.
MAX_PREFETCH = 8


class MediaResolver:
    """Resolves library entries to media objects, with caching."""

    def __init__(
        self,
        cache: MediaCache,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        store=steamstore,
        probe=url_exists,
    ) -> None:
        self.cache = cache
        self.store = store
        self._probe = probe
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._inflight: dict[str, asyncio.Task[dict[str, Any]]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_media(self, raw_entry: Any, data_saver: bool = False) -> dict[str, Any]:
        """Resolve one entry. Never raises."""
        try:
            entry = parse_entry(raw_entry)
        except Exception as exc:  # noqa: BLE001 - defensive
            logger.warning("steamview.resolver: unparseable entry: %s", exc)
            entry = None

        if entry is None:
            return media.MediaResult(key="", kind="", note="invalid-entry").to_dict()

        cached = self.cache.get(entry.cache_key)
        if cached is not None:
            return cached

        # Coalesce duplicate in-flight requests for the same entry: a
        # scroll that lands back on a game mid-fetch must not fetch twice.
        existing = self._inflight.get(entry.cache_key)
        if existing is not None:
            return await asyncio.shield(existing)

        task = asyncio.ensure_future(self._resolve_and_cache(entry, data_saver))
        self._inflight[entry.cache_key] = task
        try:
            return await task
        finally:
            self._inflight.pop(entry.cache_key, None)

    async def prefetch(self, raw_entries: Any, data_saver: bool = False) -> int:
        """Warm the cache for neighbours of the focused entry.

        Returns how many entries were actually dispatched. Errors in any
        single entry are swallowed; prefetching is best-effort by nature.
        """
        if not isinstance(raw_entries, (list, tuple)):
            return 0

        pending: list[LibraryEntry] = []
        seen: set[str] = set()
        for raw in raw_entries[:MAX_PREFETCH]:
            try:
                entry = parse_entry(raw)
            except Exception:  # noqa: BLE001
                continue
            if entry is None or entry.cache_key in seen:
                continue
            if self.cache.get(entry.cache_key) is not None:
                continue
            seen.add(entry.cache_key)
            pending.append(entry)

        if not pending:
            return 0

        await asyncio.gather(
            *(self._resolve_and_cache(entry, data_saver) for entry in pending),
            return_exceptions=True,
        )
        return len(pending)

    def clear_cache(self) -> int:
        try:
            return self.cache.clear()
        except Exception as exc:  # noqa: BLE001
            logger.warning("steamview.resolver: clear_cache failed: %s", exc)
            return 0

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _resolve_and_cache(self, entry: LibraryEntry, data_saver: bool) -> dict[str, Any]:
        try:
            async with self._semaphore:
                result = await asyncio.to_thread(self._resolve_sync, entry, data_saver)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - never surface into the UI
            logger.warning("steamview.resolver: %s failed to resolve: %s", entry.cache_key, exc)
            result = media.MediaResult(
                key=entry.cache_key,
                kind=entry.kind,
                title=entry.name,
                note="resolve-error",
            )

        # One line per resolution, at info level. This is the only view
        # into what the backend actually decided for a given game, and on
        # a Deck it is the difference between "the preview is broken" and
        # a specific, fixable cause.
        logger.info(
            "steamview: %s (%s) -> source=%s appid=%s trailer=%s screenshots=%d hero=%s%s",
            entry.name or entry.cache_key,
            entry.kind,
            result.source,
            result.resolved_appid,
            result.trailer_kind or "none",
            len(result.screenshot_urls),
            "yes" if result.hero_url else "no",
            f" note={result.note}" if result.note else "",
        )

        payload = result.to_dict()
        try:
            if result.is_empty or result.source == media.SOURCE_EMPTY:
                self.cache.put_failure(entry.cache_key, payload)
            else:
                self.cache.put(entry.cache_key, payload)
        except Exception as exc:  # noqa: BLE001
            logger.debug("steamview.resolver: could not cache %s: %s", entry.cache_key, exc)
        return payload

    def _resolve_sync(self, entry: LibraryEntry, data_saver: bool) -> media.MediaResult:
        """Blocking resolution, run on a worker thread."""
        if entry.kind == ENTRY_KIND_STEAM:
            return self._resolve_native(entry, data_saver)
        return self._resolve_shortcut(entry, data_saver)

    def _probe_fn(self, data_saver: bool):
        """The microtrailer probe, or ``None`` when video is not wanted."""
        if data_saver or self._probe is None:
            return None
        return self._probe

    def _resolve_native(self, entry: LibraryEntry, data_saver: bool) -> media.MediaResult:
        payload = self.store.fetch_appdetails(entry.appid)
        if payload is None:
            return media.build_from_art(
                key=entry.cache_key,
                kind=entry.kind,
                title=entry.name,
                hero_url=entry.hero_url or entry.capsule_url,
                extra_art=entry.extra_art,
                note="no-store-entry",
            )
        return media.build_from_appdetails(
            payload,
            key=entry.cache_key,
            kind=entry.kind,
            resolved_appid=entry.appid,
            source=media.SOURCE_APPDETAILS,
            fallback_hero=entry.hero_url or entry.capsule_url,
            fallback_title=entry.name,
            probe=self._probe_fn(data_saver),
        )

    def _resolve_shortcut(self, entry: LibraryEntry, data_saver: bool) -> media.MediaResult:
        appid = self._match_shortcut_to_appid(entry.name)
        if appid is not None:
            payload = self.store.fetch_appdetails(appid)
            if payload is not None:
                return media.build_from_appdetails(
                    payload,
                    key=entry.cache_key,
                    kind=entry.kind,
                    resolved_appid=appid,
                    source=media.SOURCE_NAME_MATCH,
                    fallback_hero=entry.hero_url or entry.capsule_url,
                    fallback_title=entry.name,
                    probe=self._probe_fn(data_saver),
                )

        return media.build_from_art(
            key=entry.cache_key,
            kind=entry.kind,
            title=entry.name,
            hero_url=entry.hero_url or entry.capsule_url,
            extra_art=entry.extra_art,
            note="no-confident-match" if appid is None else "match-had-no-store-entry",
        )

    def _match_shortcut_to_appid(self, name: str) -> int | None:
        """Best confident appid for a shortcut's display name, or ``None``."""
        for term in matching.search_terms(name):
            items: Iterable[Any] = self.store.search_store(term)
            best = matching.pick_best(name, items)
            if best is not None:
                appid, matched_name, score = best
                logger.debug(
                    "steamview.resolver: %r -> %s (%r, score %.3f)", name, appid, matched_name, score
                )
                return appid
        logger.debug("steamview.resolver: no confident store match for %r", name)
        return None
