"""Steam store language codes, and how they travel to the store.

Steam's ``l=`` parameter takes Valve's own short names, not ISO codes,
and a wrong one does not error -- it silently returns English. That
failure mode is why these tests lean on what gets *rejected*, and why the
plumbing tests assert the code actually reaches ``fetch_appdetails``
rather than being quietly dropped somewhere in between.
"""

from __future__ import annotations

import pytest

from steamview import languages
from steamview.entries import parse_entry
from steamview.resolver import MediaResolver
from steamview.settings import validate

CYBERPUNK_APPID = 1091500


class TestTheCodeList:
    def test_the_list_is_well_formed_and_has_no_duplicates(self):
        codes = [code for code, _ in languages.LANGUAGES]
        assert len(set(codes)) == len(codes)
        assert languages.DEFAULT_LANGUAGE in codes
        for code, label in languages.LANGUAGES:
            assert code.islower() and code.isalpha()
            assert label.strip()

    def test_codes_and_the_display_list_agree(self):
        assert languages.CODES == {code for code, _ in languages.LANGUAGES}

    def test_settings_choices_are_the_codes_plus_auto(self):
        assert set(languages.SETTING_CHOICES) == languages.CODES | {languages.AUTO}

    def test_the_frontend_and_backend_lists_are_identical(self):
        """A code offered in the UI that the backend rejects is a dead option."""
        import pathlib
        import re

        source = pathlib.Path(__file__).resolve().parents[1] / "src" / "languages.ts"
        found = re.findall(r'\{ code: "([a-z]+)", label: "([^"]+)" \}', source.read_text())
        assert found, "could not parse the frontend language list"
        assert found == [(code, label) for code, label in languages.LANGUAGES]


class TestNormalise:
    @pytest.mark.parametrize(
        "code", ["brazilian", "koreana", "schinese", "tchinese", "latam", "spanish"]
    )
    def test_valves_own_spellings_are_accepted(self, code):
        assert languages.normalise(code) == code

    @pytest.mark.parametrize("value", ["pt-BR", "pt", "ko", "zh-Hans", "zh-CN", "es-419", "en-US"])
    def test_iso_codes_are_rejected_rather_than_guessed_at(self, value):
        assert languages.normalise(value) is None

    @pytest.mark.parametrize("value", ["", "   ", "klingon", None, 42, [], {}, True])
    def test_junk_is_rejected(self, value):
        assert languages.normalise(value) is None

    def test_auto_is_not_a_language(self):
        """Resolving it needs the client, which the backend cannot see."""
        assert languages.normalise(languages.AUTO) is None

    def test_case_and_whitespace_are_tolerated(self):
        assert languages.normalise("  BRAZILIAN ") == "brazilian"


class TestResolve:
    def test_the_frontends_answer_wins(self):
        assert languages.resolve("brazilian", "french") == "brazilian"

    def test_the_setting_is_the_fallback(self):
        assert languages.resolve(None, "brazilian") == "brazilian"
        assert languages.resolve("klingon", "brazilian") == "brazilian"

    def test_english_is_the_floor(self):
        assert languages.resolve(None, None) == "english"
        assert languages.resolve("klingon", "auto") == "english"
        assert languages.resolve("", "") == "english"


class TestCacheKeys:
    def test_english_keys_are_unsuffixed_so_existing_caches_survive(self):
        entry = parse_entry({"appid": CYBERPUNK_APPID, "name": "Cyberpunk 2077"}, "english")
        assert entry.cache_key == f"app:{CYBERPUNK_APPID}"

    def test_the_default_is_english(self):
        entry = parse_entry({"appid": CYBERPUNK_APPID, "name": "Cyberpunk 2077"})
        assert entry.cache_key == f"app:{CYBERPUNK_APPID}"

    def test_another_language_is_a_different_entry(self):
        english = parse_entry({"appid": CYBERPUNK_APPID, "name": "X"}, "english")
        brazilian = parse_entry({"appid": CYBERPUNK_APPID, "name": "X"}, "brazilian")
        assert english.cache_key != brazilian.cache_key
        assert brazilian.cache_key == f"app:{CYBERPUNK_APPID}@brazilian"

    def test_shortcuts_are_keyed_by_language_too(self):
        raw = {"appid": 2**31 + 7, "name": "Control (Epic)"}
        assert parse_entry(raw, "english").cache_key != parse_entry(raw, "french").cache_key


class TestSettings:
    def test_the_default_is_auto(self):
        assert validate(None)["language"] == languages.AUTO

    def test_a_real_code_persists(self):
        assert validate({"language": "brazilian"})["language"] == "brazilian"

    @pytest.mark.parametrize("value", ["klingon", "pt-BR", "", None, 7])
    def test_anything_unknown_falls_back_to_auto(self, value):
        assert validate({"language": value})["language"] == languages.AUTO

    def test_dynamic_position_defaults_off(self):
        assert validate(None)["dynamic_position"] is False

    def test_dynamic_position_coerces(self):
        assert validate({"dynamic_position": "yes"})["dynamic_position"] is True
        assert validate({"dynamic_position": "nonsense"})["dynamic_position"] is False


@pytest.mark.asyncio
class TestItReachesTheStore:
    """The plumbing: a language asked for must arrive at the request."""

    async def test_the_language_reaches_appdetails(self, cache, fake_store, appdetails_payload):
        store = fake_store(appdetails={CYBERPUNK_APPID: appdetails_payload})
        resolver = MediaResolver(cache, store=store, probe=None)

        await resolver.get_media(
            {"appid": CYBERPUNK_APPID, "name": "Cyberpunk 2077"}, language="brazilian"
        )
        assert store.appdetails_languages == [(CYBERPUNK_APPID, "brazilian")]

    async def test_english_is_used_when_nothing_is_asked_for(
        self, cache, fake_store, appdetails_payload
    ):
        store = fake_store(appdetails={CYBERPUNK_APPID: appdetails_payload})
        resolver = MediaResolver(cache, store=store, probe=None)

        await resolver.get_media({"appid": CYBERPUNK_APPID, "name": "Cyberpunk 2077"})
        assert store.appdetails_languages == [(CYBERPUNK_APPID, "english")]

    async def test_two_languages_do_not_share_a_cache_entry(
        self, cache, fake_store, appdetails_payload
    ):
        store = fake_store(appdetails={CYBERPUNK_APPID: appdetails_payload})
        resolver = MediaResolver(cache, store=store, probe=None)
        entry = {"appid": CYBERPUNK_APPID, "name": "Cyberpunk 2077"}

        await resolver.get_media(entry, language="english")
        await resolver.get_media(entry, language="brazilian")
        # The second must be a real fetch, not the English one served back.
        assert store.appdetails_languages == [
            (CYBERPUNK_APPID, "english"),
            (CYBERPUNK_APPID, "brazilian"),
        ]

        # ...and each is then cached independently.
        await resolver.get_media(entry, language="english")
        await resolver.get_media(entry, language="brazilian")
        assert len(store.appdetails_languages) == 2

    async def test_shortcut_search_stays_english_while_details_localise(
        self, cache, fake_store, appdetails_payload
    ):
        """Matching is not presentation: searching in-language loses matches."""
        store = fake_store(
            appdetails={CYBERPUNK_APPID: appdetails_payload},
            searches={"Cyberpunk 2077": [{"id": CYBERPUNK_APPID, "name": "Cyberpunk 2077"}]},
        )
        resolver = MediaResolver(cache, store=store, probe=None)

        result = await resolver.get_media(
            {"appid": 2**31 + 11, "name": "Cyberpunk 2077", "app_type": 1073741824},
            language="brazilian",
        )

        assert result["resolved_appid"] == CYBERPUNK_APPID
        assert store.search_calls == ["Cyberpunk 2077"]
        assert store.appdetails_languages == [(CYBERPUNK_APPID, "brazilian")]
