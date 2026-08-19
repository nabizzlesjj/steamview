"""Title normalisation and match ranking for shortcut -> Steam appid.

Non-Steam shortcuts only give us a display name, and store launchers
decorate those names heavily ("Cyberpunk 2077 (Epic)", "DOOM Eternal -
Deluxe Edition", "Hades™"). Path B of the resolver searches Steam's
public ``storesearch`` endpoint with that name and has to decide whether
the best candidate is actually the same game.

Being wrong here is worse than finding nothing: showing the wrong game's
trailer is confusing, while showing the shortcut's own art is merely
unexciting. So the ranking is deliberately conservative and every match
must clear :data:`CONFIDENT_THRESHOLD`.
"""

from __future__ import annotations

import difflib
import re
from typing import Any, Iterable

#: Similarity a candidate must reach before we trust it enough to use its
#: trailer. Tuned to accept punctuation/edition noise but reject different
#: entries in the same franchise ("Portal" vs "Portal 2").
CONFIDENT_THRESHOLD = 0.82

# Characters that vanish rather than becoming a word break, so
# "Baldur's Gate" and "Baldurs Gate" normalise identically.
_ELIDED_CHARS = str.maketrans({"™": None, "®": None, "©": None, "'": None, "\u2019": None})

# Roman numerals are the other half of the sequel problem: "Grand Theft
# Auto V" and "Grand Theft Auto IV" are 82% similar as raw text. Mapping
# them to digits lets the numeric guard below separate them.
#
# Only two-character-and-longer numerals are converted. Single letters are
# left alone because "I", "V" and "X" are ordinary title words often
# enough ("I Am Bread", "Mega Man X") that rewriting them would create
# false matches -- and leaving them un-converted still trips the numeric
# guard when the other side has a digit, which is the outcome we want.
_ROMAN_VALUES = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}
_ROMAN_RE = re.compile(r"^(?=[ivxlcdm]{2,}$)m*(cm|cd|d?c{0,3})(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})$")


def _roman_to_int(token: str) -> int | None:
    """Convert a lowercase roman numeral of 2+ characters to its value."""
    if not _ROMAN_RE.match(token):
        return None
    total = 0
    previous = 0
    for char in reversed(token):
        value = _ROMAN_VALUES[char]
        total += value if value >= previous else -value
        previous = max(previous, value)
    return total or None

# Store/launcher decorations appended by shortcut importers.
_STORE_SUFFIX_RE = re.compile(
    r"[\s\-–—]*[\(\[]?\s*"
    r"(epic(\s+games)?(\s+store)?|gog(\.com)?|amazon(\s+games)?|"
    r"ubisoft(\s+connect)?|uplay|origin|ea(\s+app|\s+play)?|xbox(\s+cloud(\s+gaming)?)?|"
    r"microsoft(\s+store)?|game\s*pass|battle\.?net|itch(\.io)?|unifideck)"
    r"\s*[\)\]]?\s*$",
    re.IGNORECASE,
)

# Edition/bundle decorations that do not change which game this is.
_EDITION_RE = re.compile(
    r"[\s\-–—:]*[\(\[]?\s*"
    r"((game\s+of\s+the\s+year|goty|definitive|deluxe|ultimate|complete|enhanced|"
    r"special|premium|gold|legendary|anniversary|remastered|redux|director'?s\s+cut|"
    r"standard|digital|collector'?s)"
    r"(\s+edition)?|edition|bundle|pack)"
    r"\s*[\)\]]?\s*$",
    re.IGNORECASE,
)

_NON_ALNUM_RE = re.compile(r"[^0-9a-z]+")

# Tokens that carry no identifying weight when comparing titles.
_STOPWORDS = frozenset({"the", "a", "an", "of", "and"})


def normalize_for_match(title: str) -> str:
    """Lowercase, de-trademark, de-punctuate, and digitise roman numerals."""
    text = str(title or "").translate(_ELIDED_CHARS)
    text = _NON_ALNUM_RE.sub(" ", text.lower())
    tokens = []
    for token in text.split():
        value = _roman_to_int(token)
        tokens.append(str(value) if value is not None else token)
    return " ".join(tokens)


def strip_store_suffix(title: str) -> str:
    """Drop a trailing launcher/store decoration, if present."""
    previous = None
    text = str(title or "").strip()
    while text and text != previous:
        previous = text
        text = _STORE_SUFFIX_RE.sub("", text).strip()
    return text


def strip_edition_suffix(title: str) -> str:
    """Drop a trailing edition/bundle decoration, if present."""
    previous = None
    text = str(title or "").strip()
    while text and text != previous:
        previous = text
        text = _EDITION_RE.sub("", text).strip()
    return text


def search_terms(title: str) -> list[str]:
    """Ordered, de-duplicated search terms to try for one shortcut name.

    Most specific first: the raw name usually wins outright, and the
    progressively stripped variants recover the rest.
    """
    candidates = [
        str(title or "").strip(),
        strip_store_suffix(title),
        strip_edition_suffix(strip_store_suffix(title)),
    ]
    seen: set[str] = set()
    terms: list[str] = []
    for candidate in candidates:
        if candidate and candidate.casefold() not in seen:
            seen.add(candidate.casefold())
            terms.append(candidate)
    return terms


def _tokens(normalized: str) -> list[str]:
    return [tok for tok in normalized.split() if tok not in _STOPWORDS] or normalized.split()


def score_titles(query: str, candidate: str) -> float:
    """Similarity in ``[0.0, 1.0]`` between a shortcut name and a store name.

    Combines a character-level ratio (robust to small typos and spacing)
    with a token-set ratio (robust to reordering and dropped subtitles),
    then applies a hard penalty when the two titles disagree on any
    numeric token. That last rule is what keeps "Portal" off "Portal 2".
    """
    left = strip_edition_suffix(strip_store_suffix(query))
    right = strip_edition_suffix(strip_store_suffix(candidate))
    norm_left = normalize_for_match(left)
    norm_right = normalize_for_match(right)
    if not norm_left or not norm_right:
        return 0.0
    if norm_left == norm_right:
        return 1.0

    char_ratio = difflib.SequenceMatcher(None, norm_left, norm_right).ratio()

    tokens_left = set(_tokens(norm_left))
    tokens_right = set(_tokens(norm_right))
    union = tokens_left | tokens_right
    token_ratio = len(tokens_left & tokens_right) / len(union) if union else 0.0

    score = 0.6 * char_ratio + 0.4 * token_ratio

    # Sequel guard: differing numeric tokens mean different games.
    nums_left = {tok for tok in norm_left.split() if tok.isdigit()}
    nums_right = {tok for tok in norm_right.split() if tok.isdigit()}
    if nums_left != nums_right:
        score *= 0.5

    return round(min(score, 1.0), 4)


def _candidate_fields(item: Any) -> tuple[int, str] | None:
    if not isinstance(item, dict):
        return None
    try:
        appid = int(item.get("id", 0))
    except (TypeError, ValueError):
        return None
    if appid <= 0:
        return None
    name = str(item.get("name") or "").strip()
    if not name:
        return None
    return appid, name


def rank_candidates(query: str, items: Iterable[Any]) -> list[tuple[int, str, float]]:
    """Score every storesearch item, best first.

    Ties break toward the earlier item, because Steam's own search already
    orders by relevance.
    """
    ranked: list[tuple[int, int, str, float]] = []
    for position, item in enumerate(items or []):
        fields = _candidate_fields(item)
        if fields is None:
            continue
        appid, name = fields
        ranked.append((position, appid, name, score_titles(query, name)))
    ranked.sort(key=lambda row: (-row[3], row[0]))
    return [(appid, name, score) for _, appid, name, score in ranked]


def pick_best(
    query: str,
    items: Iterable[Any],
    threshold: float = CONFIDENT_THRESHOLD,
) -> tuple[int, str, float] | None:
    """The single confident match for ``query``, or ``None``."""
    ranked = rank_candidates(query, items)
    if not ranked:
        return None
    best = ranked[0]
    return best if best[2] >= threshold else None
