"""Steam's store API language codes.

Steam does not use ISO codes. Its store API takes an ``l=`` parameter
whose vocabulary is Valve's own short names -- ``brazilian`` rather than
``pt-BR``, ``koreana`` rather than ``ko``, ``schinese`` rather than
``zh-Hans``. Getting one wrong does not error; it silently returns
English, which would look like the feature simply not working.

Happily the client speaks the same vocabulary. Steam's own
``SteamClient.Settings.GetCurrentLanguage()`` returns one of these exact
strings, so the frontend can ask Steam what language it is in and pass
the answer straight through with no mapping table in between. This module
exists to *validate* that answer rather than translate it: the value ends
up in a URL sent to an external host, so it is checked against a fixed
allowlist and anything unrecognised falls back to English.

The list is Valve's, cross-checked against the ``ELanguage`` enum that
Steam's own client exposes.
"""

from __future__ import annotations

from typing import Any

#: The default, and the fallback for anything unrecognised.
DEFAULT_LANGUAGE = "english"

#: Sentinel meaning "whatever Steam itself is set to". Only ever stored
#: in settings -- it is resolved to a real code in the frontend, which is
#: the only side that can ask Steam.
AUTO = "auto"

#: Every code Steam's store API accepts, with its English name. Ordered
#: for display; English first, then alphabetically. Twenty-nine codes,
#: matching Steam's ``ELanguage`` enum one for one -- a language absent
#: here simply falls back to English, which is safe.
LANGUAGES: tuple[tuple[str, str], ...] = (
    ("english", "English"),
    ("arabic", "Arabic"),
    ("bulgarian", "Bulgarian"),
    ("schinese", "Chinese (Simplified)"),
    ("tchinese", "Chinese (Traditional)"),
    ("czech", "Czech"),
    ("danish", "Danish"),
    ("dutch", "Dutch"),
    ("finnish", "Finnish"),
    ("french", "French"),
    ("german", "German"),
    ("greek", "Greek"),
    ("hungarian", "Hungarian"),
    ("italian", "Italian"),
    ("japanese", "Japanese"),
    ("koreana", "Korean"),
    ("norwegian", "Norwegian"),
    ("polish", "Polish"),
    ("portuguese", "Portuguese"),
    ("brazilian", "Portuguese (Brazil)"),
    ("romanian", "Romanian"),
    ("russian", "Russian"),
    ("spanish", "Spanish (Spain)"),
    ("latam", "Spanish (Latin America)"),
    ("swedish", "Swedish"),
    ("thai", "Thai"),
    ("turkish", "Turkish"),
    ("ukrainian", "Ukrainian"),
    ("vietnamese", "Vietnamese"),
)

#: Fast membership test for the codes above.
CODES: frozenset[str] = frozenset(code for code, _ in LANGUAGES)

#: What settings may hold: any real code, or the auto sentinel.
SETTING_CHOICES: tuple[str, ...] = (AUTO,) + tuple(code for code, _ in LANGUAGES)


def normalise(value: Any) -> str | None:
    """Return ``value`` as a known Steam language code, or ``None``.

    Deliberately strict. This value is interpolated into a URL sent to
    Steam, so a near-miss is rejected outright rather than guessed at.
    ``auto`` is *not* a language and is rejected here too -- resolving it
    needs the client, which the backend cannot see.
    """
    if not isinstance(value, str):
        return None
    code = value.strip().lower()
    return code if code in CODES else None


def resolve(requested: Any, configured: Any = None) -> str:
    """The language to actually ask Steam for.

    ``requested`` is what the frontend resolved for this call -- it has
    asked the client, so it wins. ``configured`` is the persisted setting,
    used when the frontend sent nothing usable (an older frontend, or a
    call that raced plugin startup). Anything else is English.
    """
    return normalise(requested) or normalise(configured) or DEFAULT_LANGUAGE
