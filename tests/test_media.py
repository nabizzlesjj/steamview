"""appdetails parsing, trailer selection and microtrailer URL derivation."""

from __future__ import annotations

import pytest

from steamview import media
from steamview.media import (
    MICROTRAILER_HOSTS,
    MediaResult,
    build_from_appdetails,
    build_from_art,
    extract_screenshots,
    https,
    microtrailer_candidates,
    resolve_trailer,
)


class TestHttps:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("http://cdn/a.jpg", "https://cdn/a.jpg"),
            ("https://cdn/a.jpg", "https://cdn/a.jpg"),
            ("//cdn/a.jpg", "https://cdn/a.jpg"),
            ("  https://cdn/a.jpg  ", "https://cdn/a.jpg"),
        ],
    )
    def test_scheme_is_normalised(self, raw, expected):
        assert https(raw) == expected

    @pytest.mark.parametrize("raw", [None, "", "   ", 42, {}, "ftp://cdn/a.jpg", "/local/path.jpg"])
    def test_unusable_values_are_dropped(self, raw):
        assert https(raw) is None


class TestMicrotrailerCandidates:
    def test_one_candidate_per_cdn_host(self):
        candidates = microtrailer_candidates(256811033)
        assert len(candidates) == len(MICROTRAILER_HOSTS)
        assert all(url.endswith("/steam/apps/256811033/microtrailer.webm") for url in candidates)

    def test_cloudflare_is_tried_first(self):
        assert microtrailer_candidates(1)[0].startswith("https://cdn.cloudflare.steamstatic.com/")

    def test_numeric_strings_are_accepted(self):
        assert microtrailer_candidates("256811033") == microtrailer_candidates(256811033)

    @pytest.mark.parametrize("bad", [None, 0, -1, "", "abc", {}, []])
    def test_unusable_movie_ids_yield_nothing(self, bad):
        assert microtrailer_candidates(bad) == []


class TestResolveTrailer:
    def test_probe_confirmed_microtrailer_wins(self, appdetails_payload):
        movie = appdetails_payload["movies"][0]
        url, kind = resolve_trailer(movie, probe=lambda _: True)
        assert kind == "microtrailer"
        assert url == microtrailer_candidates(movie["id"])[0]

    def test_falls_through_to_the_next_cdn_host(self, appdetails_payload):
        movie = appdetails_payload["movies"][0]
        url, kind = resolve_trailer(movie, probe=lambda u: "akamai" in u)
        assert kind == "microtrailer"
        assert "akamai" in url

    def test_failed_probe_falls_back_to_the_published_webm(self, appdetails_payload):
        movie = appdetails_payload["movies"][0]
        url, kind = resolve_trailer(movie, probe=lambda _: False)
        assert (kind, url) == ("webm", "https://cdn.akamai.steamstatic.com/steam/apps/256811033/movie480_vp9.webm")

    def test_no_probe_skips_derivation_entirely(self, appdetails_payload):
        # Data-saver / zero-extra-request callers pass probe=None.
        _, kind = resolve_trailer(appdetails_payload["movies"][0], probe=None)
        assert kind == "webm"

    def test_a_throwing_probe_never_breaks_resolution(self, appdetails_payload):
        def explode(_):
            raise RuntimeError("network on fire")

        _, kind = resolve_trailer(appdetails_payload["movies"][0], probe=explode)
        assert kind == "webm"

    def test_mp4_is_used_when_there_is_no_webm(self):
        movie = {"id": 1, "mp4": {"480": "http://cdn/movie480.mp4"}}
        assert resolve_trailer(movie) == ("https://cdn/movie480.mp4", "mp4")

    def test_max_quality_is_used_when_480p_is_missing(self):
        movie = {"id": 1, "webm": {"max": "http://cdn/max.webm"}}
        assert resolve_trailer(movie) == ("https://cdn/max.webm", "webm")

    @pytest.mark.parametrize(
        "movie",
        [None, {}, "not a dict", {"id": 1}, {"id": 1, "webm": "not a dict"}, {"id": 1, "webm": {}}],
    )
    def test_unusable_movies_yield_no_trailer(self, movie):
        assert resolve_trailer(movie) == (None, None)


class TestMoviePicking:
    def test_the_highlight_movie_is_preferred_over_the_first(self):
        payload = {
            "movies": [
                {"id": 1, "webm": {"480": "https://cdn/one.webm"}},
                {"id": 2, "webm": {"480": "https://cdn/two.webm"}, "highlight": True},
            ]
        }
        result = build_from_appdetails(payload, key="k", kind="steam", resolved_appid=1)
        assert result.trailer_url == "https://cdn/two.webm"

    def test_first_movie_is_used_when_none_is_highlighted(self):
        payload = {"movies": [{"id": 1, "webm": {"480": "https://cdn/one.webm"}}]}
        result = build_from_appdetails(payload, key="k", kind="steam", resolved_appid=1)
        assert result.trailer_url == "https://cdn/one.webm"


class TestScreenshots:
    def test_full_size_paths_are_collected(self, appdetails_payload):
        assert extract_screenshots(appdetails_payload) == [
            "https://cdn/ss_0.1920x1080.jpg",
            "https://cdn/ss_1.1920x1080.jpg",
        ]

    def test_thumbnail_is_used_when_full_size_is_missing(self):
        assert extract_screenshots({"screenshots": [{"path_thumbnail": "https://cdn/t.jpg"}]}) == [
            "https://cdn/t.jpg"
        ]

    def test_duplicates_are_dropped(self):
        payload = {"screenshots": [{"path_full": "https://cdn/a.jpg"}] * 3}
        assert extract_screenshots(payload) == ["https://cdn/a.jpg"]

    def test_the_reel_is_capped(self):
        payload = {"screenshots": [{"path_full": f"https://cdn/{i}.jpg"} for i in range(50)]}
        assert len(extract_screenshots(payload)) == media.MAX_SCREENSHOTS

    def test_limit_is_overridable(self):
        payload = {"screenshots": [{"path_full": f"https://cdn/{i}.jpg"} for i in range(50)]}
        assert len(extract_screenshots(payload, limit=3)) == 3

    @pytest.mark.parametrize(
        "payload",
        [None, {}, "junk", {"screenshots": None}, {"screenshots": "junk"}, {"screenshots": [None, 1, "x"]}],
    )
    def test_malformed_payloads_yield_an_empty_reel(self, payload):
        assert extract_screenshots(payload) == []


class TestBuildFromAppdetails:
    def test_full_payload(self, appdetails_payload):
        result = build_from_appdetails(
            appdetails_payload, key="app:1145360", kind="steam", resolved_appid=1145360
        )
        assert result.title == "Hades"
        assert result.source == media.SOURCE_APPDETAILS
        assert result.resolved_appid == 1145360
        assert result.trailer_kind == "webm"
        assert len(result.screenshot_urls) == 2
        assert result.hero_url.endswith("/header.jpg")
        assert result.trailer_thumbnail.startswith("https://")
        assert result.is_empty is False

    def test_client_hero_is_used_when_the_payload_has_none(self):
        result = build_from_appdetails(
            {}, key="k", kind="steam", resolved_appid=1, fallback_hero="https://cdn/client-hero.jpg"
        )
        assert result.hero_url == "https://cdn/client-hero.jpg"

    def test_store_name_wins_over_the_client_name(self, appdetails_payload):
        result = build_from_appdetails(
            appdetails_payload, key="k", kind="steam", resolved_appid=1, fallback_title="Hades (Epic)"
        )
        assert result.title == "Hades"

    def test_client_name_is_used_when_the_payload_has_none(self):
        result = build_from_appdetails({}, key="k", kind="steam", resolved_appid=1, fallback_title="Hades (Epic)")
        assert result.title == "Hades (Epic)"

    @pytest.mark.parametrize("payload", [None, {}, "junk", 42, []])
    def test_a_junk_payload_produces_an_empty_but_valid_result(self, payload):
        result = build_from_appdetails(payload, key="k", kind="steam", resolved_appid=1)
        assert result.is_empty is True
        assert result.to_dict()["key"] == "k"


class TestBuildFromArt:
    def test_hero_only(self):
        result = build_from_art(
            key="shortcut:abc", kind="shortcut", title="Epic Game", hero_url="https://cdn/hero.jpg"
        )
        assert result.source == media.SOURCE_FALLBACK_ART
        assert result.hero_url == "https://cdn/hero.jpg"
        assert result.screenshot_urls == []
        assert result.is_empty is False

    def test_extra_art_becomes_the_reel(self):
        result = build_from_art(
            key="k",
            kind="shortcut",
            title="Game",
            hero_url=None,
            extra_art=["http://cdn/a.jpg", "http://cdn/a.jpg", "https://cdn/b.jpg"],
        )
        assert result.screenshot_urls == ["https://cdn/a.jpg", "https://cdn/b.jpg"]

    def test_client_local_asset_paths_survive(self):
        # SteamGridDB art applied to a shortcut can be a client-local path
        # rather than an http URL; the frontend can still render it.
        result = build_from_art(key="k", kind="shortcut", title="G", hero_url="/assets/hero.png")
        assert result.hero_url == "/assets/hero.png"

    def test_no_art_at_all_is_marked_empty(self):
        result = build_from_art(key="k", kind="shortcut", title="G", hero_url=None, note="no-confident-match")
        assert result.source == media.SOURCE_EMPTY
        assert result.is_empty is True
        assert result.note == "no-confident-match"


class TestSerialisation:
    def test_round_trip(self, appdetails_payload):
        original = build_from_appdetails(appdetails_payload, key="k", kind="steam", resolved_appid=7)
        restored = MediaResult.from_dict(original.to_dict())
        assert restored.to_dict() == original.to_dict()

    def test_to_dict_has_every_key_the_frontend_reads(self):
        keys = set(MediaResult(key="k", kind="steam").to_dict())
        assert keys == {
            "key",
            "kind",
            "title",
            "source",
            "resolved_appid",
            "trailer_url",
            "trailer_kind",
            "trailer_thumbnail",
            "screenshot_urls",
            "hero_url",
            "note",
        }

    @pytest.mark.parametrize("raw", [None, {}, "junk", {"kind": "steam"}, 42])
    def test_from_dict_rejects_unusable_records(self, raw):
        assert MediaResult.from_dict(raw) is None

    def test_from_dict_sanitises_a_corrupted_record(self):
        restored = MediaResult.from_dict(
            {"key": "k", "screenshot_urls": ["https://a.jpg", None, 7], "resolved_appid": "not an int"}
        )
        assert restored.screenshot_urls == ["https://a.jpg"]
        assert restored.resolved_appid is None
