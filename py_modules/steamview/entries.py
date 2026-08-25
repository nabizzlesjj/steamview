"""Library entry normalisation and type detection.

The frontend hands us whatever it could read off Steam's ``appStore``
overview for the highlighted item. This module turns that loose dict into
a validated :class:`LibraryEntry` and decides which resolution path it
takes.

Two signals identify a non-Steam shortcut, in order of trust:

1. ``app_type == EAppType.Shortcut`` (1073741824) -- Steam's own flag,
   read from the app overview. This is authoritative.
2. The appid falling in the synthetic shortcut range. Steam generates
   shortcut appids with the high bit set, so they are >= 2**31 when read
   as unsigned. This is the fallback for overviews that arrive without a
   usable ``app_type``.

Real Steam appids are comfortably below 2**31 (the highest published
appids are in the low millions), so the ranges do not overlap in
practice.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from .languages import DEFAULT_LANGUAGE

#: ``EAppType.Shortcut`` from Steam's client enums.
APP_TYPE_SHORTCUT = 1073741824

#: Synthetic shortcut appids have the high bit of a uint32 set.
SHORTCUT_APPID_MIN = 2**31

#: Anything at or above this is not a plausible real store appid.
MAX_REAL_APPID = 2**31 - 1

ENTRY_KIND_STEAM = "steam"
ENTRY_KIND_SHORTCUT = "shortcut"


@dataclass(frozen=True)
class LibraryEntry:
    """A normalised library item the frontend asked us to resolve."""

    appid: int
    name: str
    kind: str
    hero_url: str | None = None
    capsule_url: str | None = None
    extra_art: tuple[str, ...] = field(default_factory=tuple)
    #: Store language this entry will be resolved in. Part of the cache
    #: key, since the same game in two languages is two different
    #: payloads.
    language: str = DEFAULT_LANGUAGE

    @property
    def is_shortcut(self) -> bool:
        return self.kind == ENTRY_KIND_SHORTCUT

    @property
    def cache_key(self) -> str:
        """Stable cache key.

        Native games key by appid so the entry is shared across installs.
        Shortcuts key by a hash of their display name, because the
        synthetic appid is machine-local and changes if the shortcut is
        recreated -- but the name is what we actually resolve against.

        A non-English language is suffixed, because the cached payload
        holds a localised title, description and genres: without this,
        switching language would keep serving the old one until the entry
        expired. English is left unsuffixed on purpose, so caches written
        before languages existed stay valid rather than all missing at
        once on upgrade.
        """
        if self.kind == ENTRY_KIND_STEAM:
            base = f"app:{self.appid}"
        else:
            digest = hashlib.sha1(normalize_name(self.name).encode("utf-8")).hexdigest()[:16]
            base = f"shortcut:{digest}"
        if self.language and self.language != DEFAULT_LANGUAGE:
            return f"{base}@{self.language}"
        return base


def normalize_name(name: str) -> str:
    """Whitespace-collapsed, case-folded name, for hashing and comparison."""
    return " ".join(str(name or "").split()).casefold()


def _coerce_appid(raw: Any) -> int:
    """Best-effort int conversion, normalising negative int32 wraparound."""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 0
    if value < 0:
        # A shortcut appid read as a signed int32 comes back negative.
        value += 2**32
    if value < 0:
        return 0
    return value


def _coerce_url(raw: Any) -> str | None:
    """Sanitise an artwork URL supplied by the frontend.

    Delegates to :func:`steamview.media.client_art_url` so there is one
    definition of what may reach an ``<img>`` or ``<video>`` element.
    """
    from .media import client_art_url

    return client_art_url(raw)


def detect_kind(appid: int, app_type: Any, is_shortcut_flag: Any) -> str:
    """Decide whether an entry is a native Steam app or a shortcut."""
    if isinstance(is_shortcut_flag, bool) and is_shortcut_flag:
        return ENTRY_KIND_SHORTCUT
    try:
        if app_type is not None and int(app_type) == APP_TYPE_SHORTCUT:
            return ENTRY_KIND_SHORTCUT
    except (TypeError, ValueError):
        pass
    if appid >= SHORTCUT_APPID_MIN:
        return ENTRY_KIND_SHORTCUT
    return ENTRY_KIND_STEAM


def parse_entry(raw: Any, language: str = DEFAULT_LANGUAGE) -> LibraryEntry | None:
    """Validate a frontend-supplied entry dict.

    Returns ``None`` when the payload is unusable -- callers treat that as
    "no media", never as an error.

    ``language`` is supplied by the caller rather than read from ``raw``:
    it is a property of the *request*, not of the library item, and the
    frontend is the only side that can resolve it.
    """
    if not isinstance(raw, dict):
        return None

    appid = _coerce_appid(raw.get("appid"))
    name = " ".join(str(raw.get("name") or "").split())
    kind = detect_kind(appid, raw.get("app_type"), raw.get("is_shortcut"))

    # A native entry needs a usable appid; a shortcut needs a usable name.
    if kind == ENTRY_KIND_STEAM and not (0 < appid <= MAX_REAL_APPID):
        return None
    if kind == ENTRY_KIND_SHORTCUT and not name:
        return None

    extra = raw.get("extra_art")
    extra_urls: tuple[str, ...] = ()
    if isinstance(extra, (list, tuple)):
        extra_urls = tuple(
            url for url in (_coerce_url(item) for item in extra) if url
        )

    return LibraryEntry(
        appid=appid,
        name=name,
        kind=kind,
        hero_url=_coerce_url(raw.get("hero_url")),
        capsule_url=_coerce_url(raw.get("capsule_url")),
        extra_art=extra_urls,
        language=language or DEFAULT_LANGUAGE,
    )
