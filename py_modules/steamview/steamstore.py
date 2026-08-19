"""Thin client for the two public Steam Store endpoints we use.

These are the only external hosts the plugin ever contacts:

* ``store.steampowered.com/api/appdetails`` -- movies and screenshots for
  a known appid.
* ``store.steampowered.com/api/storesearch`` -- name to appid, for
  non-Steam shortcuts.

Plus the ``*.steamstatic.com`` CDNs the media itself is served from.
"""

from __future__ import annotations

from typing import Any

from . import http
from .compat import logger

APPDETAILS_URL = "https://store.steampowered.com/api/appdetails"
STORESEARCH_URL = "https://store.steampowered.com/api/storesearch/"


def parse_appdetails(payload: Any, appid: int) -> dict[str, Any] | None:
    """Unwrap the ``{"<appid>": {"success": bool, "data": {...}}}`` shape.

    Returns ``None`` when the app is delisted, region-locked, or simply
    has no store entry -- all of which come back as ``success: false``.
    """
    if not isinstance(payload, dict):
        return None
    entry = payload.get(str(appid))
    if not isinstance(entry, dict) or not entry.get("success"):
        return None
    data = entry.get("data")
    return data if isinstance(data, dict) else None


def parse_storesearch(payload: Any) -> list[dict[str, Any]]:
    """Unwrap the ``{"total": n, "items": [...]}`` shape."""
    if not isinstance(payload, dict):
        return []
    items = payload.get("items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def fetch_appdetails(appid: int, timeout: float = http.DEFAULT_TIMEOUT) -> dict[str, Any] | None:
    """Store metadata for ``appid``, or ``None``."""
    if not isinstance(appid, int) or appid <= 0:
        return None
    payload = http.get_json(
        APPDETAILS_URL,
        {"appids": appid, "l": "english", "cc": "us"},
        timeout=timeout,
    )
    data = parse_appdetails(payload, appid)
    if data is None:
        logger.debug("steamview.store: no appdetails for %s", appid)
    return data


def search_store(term: str, timeout: float = http.DEFAULT_TIMEOUT) -> list[dict[str, Any]]:
    """Store search results for ``term``, best-effort."""
    query = str(term or "").strip()
    if not query:
        return []
    payload = http.get_json(
        STORESEARCH_URL,
        {"term": query, "cc": "us", "l": "english"},
        timeout=timeout,
    )
    return parse_storesearch(payload)
