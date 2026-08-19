"""Turn a Steam ``appdetails`` payload into the media object the UI renders.

The frontend is deliberately dumb: it receives a fully-resolved
:class:`MediaResult` and just plays whatever is in it, in order. All the
judgement about which URL to prefer lives here.

Trailer selection, best first:

1. The **microtrailer** -- a ~6 second silent loop Steam generates for
   every movie. Its URL is *derived* from the movie id rather than
   published in the API, so it is only used after a HEAD probe confirms
   it exists. This is the ideal source: tiny, loops naturally, no audio.
2. The movie's own 480p ``webm``, which *is* published in the payload and
   therefore always correct when present.
3. The movie's 480p ``mp4``, for the rare entry with no webm variant.

Because step 1 is a guess about a CDN path Valve has never documented, it
is written as a probe over a candidate list. If Valve moves or removes
microtrailers the probe simply fails and step 2 takes over -- no code
change, no broken preview.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

#: CDN hosts that serve Steam's app media, in preference order.
#: All three front the same origin; listing several survives one of them
#: being unreachable or DNS-blocked on a given network.
MICROTRAILER_HOSTS: tuple[str, ...] = (
    "https://cdn.cloudflare.steamstatic.com",
    "https://cdn.akamai.steamstatic.com",
    "https://shared.fastly.steamstatic.com",
)

#: Path template for the derived microtrailer. UNVERIFIED against a live
#: CDN -- see the module docstring and DESIGN.md. Probed, never assumed.
MICROTRAILER_PATH = "/steam/apps/{movie_id}/microtrailer.webm"

#: More than this and the reel is longer than anyone will ever watch.
MAX_SCREENSHOTS = 12

SOURCE_APPDETAILS = "appdetails"
SOURCE_NAME_MATCH = "name-match"
SOURCE_FALLBACK_ART = "fallback-art"
SOURCE_EMPTY = "empty"


@dataclass
class MediaResult:
    """Everything the overlay needs to render one library entry."""

    key: str
    kind: str
    title: str = ""
    source: str = SOURCE_EMPTY
    resolved_appid: int | None = None
    trailer_url: str | None = None
    trailer_kind: str | None = None
    trailer_thumbnail: str | None = None
    screenshot_urls: list[str] = field(default_factory=list)
    hero_url: str | None = None
    note: str | None = None

    @property
    def is_empty(self) -> bool:
        return not (self.trailer_url or self.screenshot_urls or self.hero_url)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "kind": self.kind,
            "title": self.title,
            "source": self.source,
            "resolved_appid": self.resolved_appid,
            "trailer_url": self.trailer_url,
            "trailer_kind": self.trailer_kind,
            "trailer_thumbnail": self.trailer_thumbnail,
            "screenshot_urls": list(self.screenshot_urls),
            "hero_url": self.hero_url,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> "MediaResult | None":
        if not isinstance(raw, dict) or not raw.get("key"):
            return None
        screenshots = raw.get("screenshot_urls")
        return cls(
            key=str(raw["key"]),
            kind=str(raw.get("kind") or ""),
            title=str(raw.get("title") or ""),
            source=str(raw.get("source") or SOURCE_EMPTY),
            resolved_appid=raw.get("resolved_appid") if isinstance(raw.get("resolved_appid"), int) else None,
            trailer_url=raw.get("trailer_url") or None,
            trailer_kind=raw.get("trailer_kind") or None,
            trailer_thumbnail=raw.get("trailer_thumbnail") or None,
            screenshot_urls=[str(url) for url in screenshots if isinstance(url, str)]
            if isinstance(screenshots, list)
            else [],
            hero_url=raw.get("hero_url") or None,
            note=raw.get("note") or None,
        )


def https(url: Any) -> str | None:
    """Force a media URL to https, or drop it if it is not usable."""
    if not isinstance(url, str):
        return None
    text = url.strip()
    if not text:
        return None
    if text.startswith("//"):
        return "https:" + text
    if text.startswith("http://"):
        return "https://" + text[len("http://") :]
    if text.startswith("https://"):
        return text
    return None


def microtrailer_candidates(movie_id: Any) -> list[str]:
    """Every CDN URL the microtrailer for ``movie_id`` might live at."""
    try:
        identifier = int(movie_id)
    except (TypeError, ValueError):
        return []
    if identifier <= 0:
        return []
    path = MICROTRAILER_PATH.format(movie_id=identifier)
    return [host + path for host in MICROTRAILER_HOSTS]


def _pick_movie(movies: Any) -> dict[str, Any] | None:
    """Steam's own highlight movie, else the first one."""
    if not isinstance(movies, list):
        return None
    usable = [movie for movie in movies if isinstance(movie, dict)]
    if not usable:
        return None
    for movie in usable:
        if movie.get("highlight"):
            return movie
    return usable[0]


def _variant(movie: dict[str, Any], container: str) -> str | None:
    """The 480p variant of ``container``, falling back to ``max``."""
    block = movie.get(container)
    if not isinstance(block, dict):
        return None
    for quality in ("480", "max"):
        url = https(block.get(quality))
        if url:
            return url
    return None


def resolve_trailer(
    movie: dict[str, Any] | None,
    probe: Callable[[str], bool] | None = None,
) -> tuple[str | None, str | None]:
    """Pick the best playable trailer URL and label its kind.

    ``probe`` is called only for the derived microtrailer candidates. Pass
    ``None`` to skip probing entirely (data saver, or callers that would
    rather spend zero extra requests).
    """
    if not isinstance(movie, dict):
        return None, None

    if probe is not None:
        for candidate in microtrailer_candidates(movie.get("id")):
            try:
                if probe(candidate):
                    return candidate, "microtrailer"
            except Exception:  # noqa: BLE001 - a probe must never break resolution
                continue

    webm = _variant(movie, "webm")
    if webm:
        return webm, "webm"
    mp4 = _variant(movie, "mp4")
    if mp4:
        return mp4, "mp4"
    return None, None


def extract_screenshots(payload: Any, limit: int = MAX_SCREENSHOTS) -> list[str]:
    """Full-size screenshot URLs from an appdetails payload."""
    screenshots = payload.get("screenshots") if isinstance(payload, dict) else None
    if not isinstance(screenshots, list):
        return []
    urls: list[str] = []
    for item in screenshots:
        if not isinstance(item, dict):
            continue
        url = https(item.get("path_full")) or https(item.get("path_thumbnail"))
        if url and url not in urls:
            urls.append(url)
        if len(urls) >= limit:
            break
    return urls


def build_from_appdetails(
    payload: Any,
    *,
    key: str,
    kind: str,
    resolved_appid: int,
    source: str = SOURCE_APPDETAILS,
    fallback_hero: str | None = None,
    fallback_title: str = "",
    probe: Callable[[str], bool] | None = None,
) -> MediaResult:
    """Assemble a :class:`MediaResult` from one appdetails ``data`` dict."""
    data = payload if isinstance(payload, dict) else {}
    movie = _pick_movie(data.get("movies"))
    trailer_url, trailer_kind = resolve_trailer(movie, probe=probe)

    return MediaResult(
        key=key,
        kind=kind,
        title=str(data.get("name") or fallback_title or ""),
        source=source,
        resolved_appid=resolved_appid,
        trailer_url=trailer_url,
        trailer_kind=trailer_kind,
        trailer_thumbnail=https(movie.get("thumbnail")) if isinstance(movie, dict) else None,
        screenshot_urls=extract_screenshots(data),
        hero_url=https(data.get("header_image")) or fallback_hero,
    )


def build_from_art(
    *,
    key: str,
    kind: str,
    title: str,
    hero_url: str | None,
    extra_art: Sequence[str] | Iterable[str] = (),
    note: str | None = None,
) -> MediaResult:
    """The Path B floor: whatever artwork the client already had."""
    reel: list[str] = []
    for url in extra_art or ():
        clean = https(url) or (url if isinstance(url, str) and url.strip() else None)
        if clean and clean not in reel:
            reel.append(clean)
        if len(reel) >= MAX_SCREENSHOTS:
            break

    hero = https(hero_url) or (hero_url if isinstance(hero_url, str) and hero_url.strip() else None)
    return MediaResult(
        key=key,
        kind=kind,
        title=title,
        source=SOURCE_FALLBACK_ART if (hero or reel) else SOURCE_EMPTY,
        screenshot_urls=reel,
        hero_url=hero,
        note=note,
    )
