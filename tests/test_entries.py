"""Entry-type detection and normalisation."""

from __future__ import annotations

import pytest

from steamview.entries import (
    APP_TYPE_SHORTCUT,
    ENTRY_KIND_SHORTCUT,
    ENTRY_KIND_STEAM,
    LibraryEntry,
    detect_kind,
    parse_entry,
)


class TestDetectKind:
    def test_ordinary_appid_is_native(self):
        assert detect_kind(1145360, None, None) == ENTRY_KIND_STEAM

    def test_app_type_flag_wins_over_low_appid(self):
        # A shortcut whose overview reports a small appid is still a shortcut.
        assert detect_kind(570, APP_TYPE_SHORTCUT, None) == ENTRY_KIND_SHORTCUT

    def test_explicit_boolean_flag_is_honoured(self):
        assert detect_kind(570, None, True) == ENTRY_KIND_SHORTCUT

    def test_high_appid_range_implies_shortcut(self):
        assert detect_kind(2749847623, None, None) == ENTRY_KIND_SHORTCUT

    @pytest.mark.parametrize("junk", ["nonsense", {}, [], object()])
    def test_unusable_app_type_falls_back_to_appid_range(self, junk):
        assert detect_kind(1145360, junk, None) == ENTRY_KIND_STEAM
        assert detect_kind(2749847623, junk, None) == ENTRY_KIND_SHORTCUT


class TestParseEntry:
    def test_native_entry(self):
        entry = parse_entry({"appid": 1145360, "name": "Hades"})
        assert entry == LibraryEntry(appid=1145360, name="Hades", kind=ENTRY_KIND_STEAM)
        assert entry.is_shortcut is False
        assert entry.cache_key == "app:1145360"

    def test_shortcut_entry_keys_by_name_hash(self):
        entry = parse_entry({"appid": 2749847623, "name": "Cyberpunk 2077"})
        assert entry.is_shortcut is True
        assert entry.cache_key.startswith("shortcut:")

    def test_shortcut_key_is_stable_across_regenerated_appids(self):
        # Unifideck shortcut appids are machine-local and change if the
        # shortcut is recreated; the cache key must not.
        first = parse_entry({"appid": 2749847623, "name": "Cyberpunk 2077"})
        second = parse_entry({"appid": 3010000001, "name": "  cyberpunk 2077  "})
        assert first.cache_key == second.cache_key

    def test_different_shortcuts_get_different_keys(self):
        first = parse_entry({"appid": 2749847623, "name": "Cyberpunk 2077"})
        second = parse_entry({"appid": 2749847624, "name": "Hades"})
        assert first.cache_key != second.cache_key

    def test_negative_appid_is_unwrapped_from_signed_int32(self):
        entry = parse_entry({"appid": -1545119673, "name": "Some GOG Game"})
        assert entry.appid == 2749847623
        assert entry.is_shortcut is True

    def test_urls_are_forced_to_https(self):
        entry = parse_entry(
            {
                "appid": 1145360,
                "name": "Hades",
                "hero_url": "http://cdn/hero.jpg",
                "capsule_url": "//cdn/capsule.jpg",
                "extra_art": ["http://cdn/a.jpg", None, 7, "https://cdn/b.jpg"],
            }
        )
        assert entry.hero_url == "https://cdn/hero.jpg"
        assert entry.capsule_url == "https://cdn/capsule.jpg"
        assert entry.extra_art == ("https://cdn/a.jpg", "https://cdn/b.jpg")

    def test_name_whitespace_is_collapsed(self):
        assert parse_entry({"appid": 1, "name": "  Half   Life  "}).name == "Half Life"

    @pytest.mark.parametrize(
        "raw",
        [
            None,
            "not a dict",
            [],
            {},
            {"appid": 0, "name": "No appid and native"},
            {"appid": "abc", "name": ""},
            {"appid": 2749847623, "name": ""},  # shortcut with no name is unresolvable
        ],
    )
    def test_unusable_payloads_return_none(self, raw):
        assert parse_entry(raw) is None

    def test_shortcut_without_appid_still_parses_when_named(self):
        entry = parse_entry({"appid": 0, "name": "Epic Game", "is_shortcut": True})
        assert entry is not None
        assert entry.kind == ENTRY_KIND_SHORTCUT


class TestEntryUrlSanitisation:
    """The frontend reads artwork URLs off Steam's app overview, and on a
    non-Steam shortcut that artwork is whatever the user configured."""

    def test_hostile_schemes_are_dropped(self):
        entry = parse_entry(
            {
                "appid": 2749847623,
                "name": "Shortcut",
                "hero_url": "javascript:alert(1)",
                "capsule_url": "data:text/html,x",
                "extra_art": ["file:///etc/passwd", "https://cdn/ok.jpg"],
            }
        )
        assert entry.hero_url is None
        assert entry.capsule_url is None
        assert entry.extra_art == ("https://cdn/ok.jpg",)

    def test_client_local_paths_are_kept(self):
        entry = parse_entry({"appid": 1, "name": "G", "hero_url": "/assets/hero.png"})
        assert entry.hero_url == "/assets/hero.png"
