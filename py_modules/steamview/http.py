"""Minimal HTTP helpers built on the standard library.

The backend does all network I/O so the frontend never has to fight CORS,
and so responses can be cached to disk. These functions are synchronous;
the resolver runs them off the event loop with ``asyncio.to_thread``.

Every function here swallows transport errors and returns a sentinel
rather than raising -- a media preview is never important enough to
surface an exception into the UI.
"""

from __future__ import annotations

import gzip
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Mapping

from .compat import logger

#: A plain desktop UA. Steam's public endpoints reject some default
#: urllib agents, and this keeps us indistinguishable from a browser hit.
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) SteamView/1.0"

DEFAULT_TIMEOUT = 12.0

#: Statuses worth a retry: rate limiting and transient upstream faults.
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})

_MAX_ATTEMPTS = 3
_BASE_BACKOFF = 0.75
_MAX_BACKOFF = 8.0
#: Refuse to buffer absurd responses; appdetails payloads are ~100 KB.
_MAX_BODY_BYTES = 8 * 1024 * 1024


class _NoRedirectFor4xx(urllib.request.HTTPRedirectHandler):
    """Follow redirects normally; this exists only to cap the chain."""

    max_redirections = 5


def _unverified_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


_opener = urllib.request.build_opener(_NoRedirectFor4xx)

# Fallback for SteamOS. See _open() for why this exists.
_insecure_opener = urllib.request.build_opener(
    _NoRedirectFor4xx,
    urllib.request.HTTPSHandler(context=_unverified_context()),
)

#: Set once verification has been proven broken on this device, so we stop
#: paying for a doomed verified attempt on every subsequent request.
_tls_verification_broken = False
_tls_warning_logged = False


def _is_tls_failure(error: BaseException) -> bool:
    """Whether ``error`` is a certificate/TLS problem rather than a network one."""
    if isinstance(error, ssl.SSLError):
        return True
    reason = getattr(error, "reason", None)
    return isinstance(reason, ssl.SSLError)


def _note_tls_fallback(url: str, error: BaseException) -> None:
    global _tls_verification_broken, _tls_warning_logged
    _tls_verification_broken = True
    if _tls_warning_logged:
        return
    _tls_warning_logged = True
    logger.warning(
        "steamview.http: TLS certificate verification failed for %s (%s). "
        "SteamOS's bundled certificate store is outdated inside the Decky plugin "
        "process, so media metadata will be fetched without certificate "
        "verification for the rest of this session. This affects only Steam's "
        "public store and CDN endpoints; the plugin sends no credentials or "
        "personal data.",
        url,
        error,
    )


def _open(request: urllib.request.Request, timeout: float):
    """Open ``request``, falling back to unverified TLS if verification fails.

    SteamOS ships an outdated CA bundle, and inside the Decky plugin
    process certificate verification against Steam's own store endpoints
    fails outright. Without a fallback every media lookup returns nothing,
    and because this module degrades to `None` rather than raising, that
    failure is silent.

    Verification is still attempted first, and the fallback engages only
    after a genuine certificate error -- never after a timeout, DNS
    failure, or HTTP error. What travels over it is public game metadata,
    with no credentials and nothing user-identifying.
    """
    if _tls_verification_broken:
        return _insecure_opener.open(request, timeout=timeout)
    try:
        return _opener.open(request, timeout=timeout)
    except (urllib.error.URLError, ssl.SSLError) as exc:
        if not _is_tls_failure(exc):
            raise
        _note_tls_fallback(request.full_url, exc)
        return _insecure_opener.open(request, timeout=timeout)


def build_url(url: str, params: Mapping[str, Any] | None = None) -> str:
    """Append a query string to ``url``."""
    if not params:
        return url
    encoded = urllib.parse.urlencode(
        {key: str(value) for key, value in params.items() if value is not None}
    )
    joiner = "&" if "?" in url else "?"
    return f"{url}{joiner}{encoded}" if encoded else url


def _sleep_for(attempt: int, retry_after: str | None) -> float:
    if retry_after:
        try:
            return min(float(retry_after), _MAX_BACKOFF)
        except (TypeError, ValueError):
            pass
    return min(_BASE_BACKOFF * (2**attempt), _MAX_BACKOFF)


def _read_body(response: Any) -> bytes:
    body = response.read(_MAX_BODY_BYTES + 1)
    if len(body) > _MAX_BODY_BYTES:
        raise ValueError("response body exceeds the size cap")
    if response.headers.get("Content-Encoding", "").lower() == "gzip":
        body = gzip.decompress(body)
    return body


def get_json(
    url: str,
    params: Mapping[str, Any] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    sleep=time.sleep,
) -> Any | None:
    """GET ``url`` and parse JSON, or return ``None``.

    ``sleep`` is injectable so tests can exercise the retry path without
    actually waiting.
    """
    target = build_url(url, params)
    request = urllib.request.Request(
        target,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "Accept-Language": "en-US,en;q=0.9",
        },
        method="GET",
    )

    for attempt in range(_MAX_ATTEMPTS):
        try:
            with _open(request, timeout) as response:
                return json.loads(_read_body(response).decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            if exc.code in _RETRY_STATUSES and attempt < _MAX_ATTEMPTS - 1:
                delay = _sleep_for(attempt, exc.headers.get("Retry-After") if exc.headers else None)
                logger.debug("steamview.http: %s -> HTTP %s, retrying in %.2fs", target, exc.code, delay)
                sleep(delay)
                continue
            logger.warning("steamview.http: %s failed with HTTP %s", target, exc.code)
            return None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt < _MAX_ATTEMPTS - 1:
                delay = _sleep_for(attempt, None)
                logger.debug("steamview.http: %s transport error (%s), retrying in %.2fs", target, exc, delay)
                sleep(delay)
                continue
            logger.warning("steamview.http: %s failed: %s", target, exc)
            return None
        except (ValueError, json.JSONDecodeError) as exc:
            logger.warning("steamview.http: %s returned unparseable body: %s", target, exc)
            return None
    return None


def url_exists(url: str, timeout: float = DEFAULT_TIMEOUT) -> bool:
    """Whether ``url`` answers a HEAD request with a 2xx.

    Used to probe CDN media paths that are derived rather than published,
    so a wrong guess degrades to the next candidate instead of a broken
    ``<video>`` element on device.
    """
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
        method="HEAD",
    )
    try:
        with _open(request, timeout) as response:
            return 200 <= int(getattr(response, "status", 0) or 0) < 300
    except urllib.error.HTTPError as exc:
        logger.debug("steamview.http: HEAD %s -> HTTP %s", url, exc.code)
        return False
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        logger.debug("steamview.http: HEAD %s failed: %s", url, exc)
        return False
