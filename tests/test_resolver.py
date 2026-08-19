"""End-to-end resolution: Path A, Path B, caching, and failure handling.

All network access is replaced by ``FakeStore``. The contract these tests
pin down is that *no* input can make the resolver raise -- the worst case
is a well-formed, empty media object.
"""

from __future__ import annotations

import asyncio

import pytest

from steamview import media
from steamview.resolver import MediaResolver

CYBERPUNK_APPID = 1091500
HADES_APPID = 1145360

pytestmark = pytest.mark.asyncio


def make_resolver(cache, fake_store, appdetails=None, searches=None, probe=None):
    store = fake_store(appdetails=appdetails, searches=searches)
    return MediaResolver(cache, store=store, probe=probe), store


@pytest.fixture
def hades_details(appdetails_payload):
    return {HADES_APPID: appdetails_payload}


class TestPathANative:
    async def test_a_native_game_resolves_from_appdetails(self, cache, fake_store, hades_details):
        resolver, store = make_resolver(cache, fake_store, appdetails=hades_details)
        result = await resolver.get_media({"appid": HADES_APPID, "name": "Hades"})

        assert result["source"] == media.SOURCE_APPDETAILS
        assert result["resolved_appid"] == HADES_APPID
        assert result["trailer_url"].endswith("movie480_vp9.webm")
        assert len(result["screenshot_urls"]) == 2
        assert store.appdetails_calls == [HADES_APPID]
        assert store.search_calls == []

    async def test_a_native_game_never_hits_the_search_endpoint(self, cache, fake_store, hades_details):
        resolver, store = make_resolver(cache, fake_store, appdetails=hades_details)
        await resolver.get_media({"appid": HADES_APPID, "name": "Hades"})
        assert store.search_calls == []

    async def test_a_native_game_with_no_store_entry_falls_back_to_client_art(self, cache, fake_store):
        resolver, _ = make_resolver(cache, fake_store, appdetails={})
        result = await resolver.get_media(
            {"appid": 9999999, "name": "Delisted Thing", "hero_url": "https://cdn/hero.jpg"}
        )
        assert result["source"] == media.SOURCE_FALLBACK_ART
        assert result["hero_url"] == "https://cdn/hero.jpg"
        assert result["note"] == "no-store-entry"

    async def test_the_microtrailer_probe_runs_for_native_games(self, cache, fake_store, hades_details):
        resolver, _ = make_resolver(cache, fake_store, appdetails=hades_details, probe=lambda _: True)
        result = await resolver.get_media({"appid": HADES_APPID, "name": "Hades"})
        assert result["trailer_kind"] == "microtrailer"


class TestPathBShortcut:
    async def test_a_shortcut_resolves_by_name_to_a_real_appid(self, cache, fake_store, appdetails_payload):
        resolver, store = make_resolver(
            cache,
            fake_store,
            appdetails={CYBERPUNK_APPID: {**appdetails_payload, "name": "Cyberpunk 2077"}},
            searches={"Cyberpunk 2077 (Epic)": [{"id": CYBERPUNK_APPID, "name": "Cyberpunk 2077"}]},
        )
        result = await resolver.get_media({"appid": 2749847623, "name": "Cyberpunk 2077 (Epic)"})

        assert result["source"] == media.SOURCE_NAME_MATCH
        assert result["resolved_appid"] == CYBERPUNK_APPID
        assert result["trailer_url"] is not None
        assert store.search_calls == ["Cyberpunk 2077 (Epic)"]

    async def test_progressively_stripped_terms_are_tried(self, cache, fake_store, appdetails_payload):
        # The decorated name finds nothing; the stripped one does.
        resolver, store = make_resolver(
            cache,
            fake_store,
            appdetails={CYBERPUNK_APPID: appdetails_payload},
            searches={"Cyberpunk 2077": [{"id": CYBERPUNK_APPID, "name": "Cyberpunk 2077"}]},
        )
        result = await resolver.get_media({"appid": 2749847623, "name": "Cyberpunk 2077 (Epic)"})

        assert result["resolved_appid"] == CYBERPUNK_APPID
        assert store.search_calls == ["Cyberpunk 2077 (Epic)", "Cyberpunk 2077"]

    async def test_an_unconfident_match_falls_back_to_shortcut_art(self, cache, fake_store):
        resolver, _ = make_resolver(
            cache,
            fake_store,
            searches={"Some Obscure Launcher Game": [{"id": 1, "name": "Totally Different Game"}]},
        )
        result = await resolver.get_media(
            {
                "appid": 2749847623,
                "name": "Some Obscure Launcher Game",
                "hero_url": "https://sgdb/hero.png",
            }
        )
        assert result["source"] == media.SOURCE_FALLBACK_ART
        assert result["hero_url"] == "https://sgdb/hero.png"
        assert result["note"] == "no-confident-match"
        assert result["resolved_appid"] is None

    async def test_the_wrong_sequel_is_never_matched(self, cache, fake_store, appdetails_payload):
        resolver, _ = make_resolver(
            cache,
            fake_store,
            appdetails={620: appdetails_payload},
            searches={"Portal": [{"id": 620, "name": "Portal 2"}]},
        )
        result = await resolver.get_media({"appid": 2749847623, "name": "Portal"})
        assert result["resolved_appid"] is None
        assert result["source"] == media.SOURCE_EMPTY

    async def test_extra_art_becomes_a_screenshot_reel(self, cache, fake_store):
        resolver, _ = make_resolver(cache, fake_store)
        result = await resolver.get_media(
            {
                "appid": 2749847623,
                "name": "Unmatchable Game",
                "extra_art": ["https://sgdb/1.png", "https://sgdb/2.png"],
            }
        )
        assert result["screenshot_urls"] == ["https://sgdb/1.png", "https://sgdb/2.png"]

    async def test_a_match_whose_store_entry_vanished_falls_back(self, cache, fake_store):
        resolver, _ = make_resolver(
            cache,
            fake_store,
            appdetails={},  # the matched appid has no appdetails
            searches={"Hades": [{"id": HADES_APPID, "name": "Hades"}]},
        )
        result = await resolver.get_media(
            {"appid": 2749847623, "name": "Hades", "hero_url": "https://sgdb/hero.png"}
        )
        assert result["source"] == media.SOURCE_FALLBACK_ART
        assert result["note"] == "match-had-no-store-entry"

    async def test_a_shortcut_with_no_art_at_all_is_empty_but_well_formed(self, cache, fake_store):
        resolver, _ = make_resolver(cache, fake_store)
        result = await resolver.get_media({"appid": 2749847623, "name": "Nothing At All"})
        assert result["source"] == media.SOURCE_EMPTY
        assert result["screenshot_urls"] == []
        assert result["hero_url"] is None
        assert set(result) >= {"key", "kind", "trailer_url", "screenshot_urls", "hero_url"}


class TestCaching:
    async def test_a_second_request_is_served_from_cache(self, cache, fake_store, hades_details):
        resolver, store = make_resolver(cache, fake_store, appdetails=hades_details)
        entry = {"appid": HADES_APPID, "name": "Hades"}
        first = await resolver.get_media(entry)
        second = await resolver.get_media(entry)
        assert first == second
        assert store.appdetails_calls == [HADES_APPID]

    async def test_failures_are_cached_too(self, cache, fake_store):
        resolver, store = make_resolver(cache, fake_store, appdetails={})
        entry = {"appid": 999, "name": "Nope"}
        await resolver.get_media(entry)
        await resolver.get_media(entry)
        assert len(store.appdetails_calls) == 1

    async def test_a_failure_is_re_fetched_once_its_shorter_ttl_lapses(
        self, cache, clock, fake_store, hades_details
    ):
        resolver, store = make_resolver(cache, fake_store, appdetails={})
        entry = {"appid": HADES_APPID, "name": "Hades"}
        await resolver.get_media(entry)

        clock.advance(cache.negative_ttl + 1)
        store.appdetails = hades_details
        result = await resolver.get_media(entry)

        assert result["source"] == media.SOURCE_APPDETAILS
        assert len(store.appdetails_calls) == 2

    async def test_a_success_survives_past_the_negative_ttl(self, cache, clock, fake_store, hades_details):
        resolver, store = make_resolver(cache, fake_store, appdetails=hades_details)
        entry = {"appid": HADES_APPID, "name": "Hades"}
        await resolver.get_media(entry)
        clock.advance(cache.negative_ttl + 1)
        await resolver.get_media(entry)
        assert len(store.appdetails_calls) == 1

    async def test_concurrent_requests_for_one_entry_fetch_once(self, cache, fake_store, hades_details):
        resolver, store = make_resolver(cache, fake_store, appdetails=hades_details)
        entry = {"appid": HADES_APPID, "name": "Hades"}
        results = await asyncio.gather(*(resolver.get_media(entry) for _ in range(6)))
        assert len({r["key"] for r in results}) == 1
        assert store.appdetails_calls == [HADES_APPID]

    async def test_clear_cache_forces_a_re_fetch(self, cache, fake_store, hades_details):
        resolver, store = make_resolver(cache, fake_store, appdetails=hades_details)
        entry = {"appid": HADES_APPID, "name": "Hades"}
        await resolver.get_media(entry)
        assert resolver.clear_cache() == 1
        await resolver.get_media(entry)
        assert len(store.appdetails_calls) == 2

    async def test_native_and_shortcut_entries_do_not_share_a_key(self, cache, fake_store, hades_details):
        resolver, _ = make_resolver(cache, fake_store, appdetails=hades_details)
        native = await resolver.get_media({"appid": HADES_APPID, "name": "Hades"})
        shortcut = await resolver.get_media({"appid": 2749847623, "name": "Hades"})
        assert native["key"] != shortcut["key"]


class TestPrefetch:
    async def test_neighbours_are_warmed(self, cache, fake_store, appdetails_payload):
        resolver, store = make_resolver(
            cache, fake_store, appdetails={1: appdetails_payload, 2: appdetails_payload}
        )
        assert await resolver.prefetch([{"appid": 1, "name": "One"}, {"appid": 2, "name": "Two"}]) == 2
        assert sorted(store.appdetails_calls) == [1, 2]

    async def test_a_prefetched_entry_is_then_served_from_cache(self, cache, fake_store, appdetails_payload):
        resolver, store = make_resolver(cache, fake_store, appdetails={1: appdetails_payload})
        await resolver.prefetch([{"appid": 1, "name": "One"}])
        await resolver.get_media({"appid": 1, "name": "One"})
        assert store.appdetails_calls == [1]

    async def test_already_cached_entries_are_skipped(self, cache, fake_store, appdetails_payload):
        resolver, store = make_resolver(cache, fake_store, appdetails={1: appdetails_payload})
        await resolver.get_media({"appid": 1, "name": "One"})
        assert await resolver.prefetch([{"appid": 1, "name": "One"}]) == 0
        assert store.appdetails_calls == [1]

    async def test_duplicates_within_one_call_are_collapsed(self, cache, fake_store, appdetails_payload):
        resolver, store = make_resolver(cache, fake_store, appdetails={1: appdetails_payload})
        assert await resolver.prefetch([{"appid": 1, "name": "One"}] * 5) == 1
        assert store.appdetails_calls == [1]

    async def test_the_batch_is_capped(self, cache, fake_store, appdetails_payload):
        from steamview.resolver import MAX_PREFETCH

        resolver, store = make_resolver(
            cache, fake_store, appdetails={i: appdetails_payload for i in range(1, 40)}
        )
        entries = [{"appid": i, "name": f"Game {i}"} for i in range(1, 40)]
        assert await resolver.prefetch(entries) == MAX_PREFETCH
        assert len(store.appdetails_calls) == MAX_PREFETCH

    @pytest.mark.parametrize("entries", [None, "junk", 42, {}, [], [None, "junk", {}]])
    async def test_malformed_batches_are_safe(self, cache, fake_store, entries):
        resolver, _ = make_resolver(cache, fake_store)
        assert await resolver.prefetch(entries) == 0


class TestFailureIsolation:
    @pytest.mark.parametrize("entry", [None, "junk", 42, {}, [], {"appid": 0, "name": ""}])
    async def test_an_unusable_entry_returns_a_well_formed_empty_result(self, cache, fake_store, entry):
        resolver, _ = make_resolver(cache, fake_store)
        result = await resolver.get_media(entry)
        assert result["note"] == "invalid-entry"
        assert result["trailer_url"] is None
        assert result["screenshot_urls"] == []

    async def test_a_store_that_raises_does_not_propagate(self, cache, fake_store):
        resolver, store = make_resolver(cache, fake_store)

        def explode(*args, **kwargs):
            raise RuntimeError("upstream on fire")

        store.fetch_appdetails = explode
        result = await resolver.get_media({"appid": HADES_APPID, "name": "Hades"})
        assert result["note"] == "resolve-error"
        assert result["key"] == f"app:{HADES_APPID}"

    async def test_a_search_that_raises_does_not_propagate(self, cache, fake_store):
        resolver, store = make_resolver(cache, fake_store)

        def explode(*args, **kwargs):
            raise RuntimeError("upstream on fire")

        store.search_store = explode
        result = await resolver.get_media({"appid": 2749847623, "name": "Some Game"})
        assert result["note"] == "resolve-error"

    async def test_a_store_returning_garbage_does_not_propagate(self, cache, fake_store):
        resolver, _ = make_resolver(cache, fake_store, appdetails={HADES_APPID: "not a dict"})
        result = await resolver.get_media({"appid": HADES_APPID, "name": "Hades"})
        assert result["trailer_url"] is None
        assert result["key"] == f"app:{HADES_APPID}"

    async def test_an_unwritable_cache_does_not_break_resolution(self, cache, fake_store, hades_details):
        resolver, _ = make_resolver(cache, fake_store, appdetails=hades_details)

        def explode(*args, **kwargs):
            raise OSError("read-only filesystem")

        cache.put = explode
        cache.put_failure = explode
        result = await resolver.get_media({"appid": HADES_APPID, "name": "Hades"})
        assert result["source"] == media.SOURCE_APPDETAILS

    async def test_clear_cache_survives_an_exploding_cache(self, cache, fake_store):
        resolver, _ = make_resolver(cache, fake_store)

        def explode():
            raise OSError("nope")

        cache.clear = explode
        assert resolver.clear_cache() == 0


class TestDataSaver:
    async def test_data_saver_skips_the_microtrailer_probe(self, cache, fake_store, hades_details):
        probed: list[str] = []

        def probe(url):
            probed.append(url)
            return True

        resolver, _ = make_resolver(cache, fake_store, appdetails=hades_details, probe=probe)
        result = await resolver.get_media({"appid": HADES_APPID, "name": "Hades"}, data_saver=True)

        assert probed == []
        # The published webm is still returned; the frontend is what
        # decides not to play it in data-saver mode.
        assert result["trailer_kind"] == "webm"

    async def test_probing_happens_when_data_saver_is_off(self, cache, fake_store, hades_details):
        probed: list[str] = []
        resolver, _ = make_resolver(
            cache, fake_store, appdetails=hades_details, probe=lambda u: probed.append(u) or True
        )
        await resolver.get_media({"appid": HADES_APPID, "name": "Hades"}, data_saver=False)
        assert probed


class TestConcurrencyLimit:
    async def test_concurrent_resolutions_are_capped(self, cache, fake_store, appdetails_payload):
        peak = 0
        active = 0
        lock = asyncio.Lock()

        store = fake_store(appdetails={i: appdetails_payload for i in range(1, 40)})
        original = store.fetch_appdetails

        def counting_fetch(appid, timeout=None):
            nonlocal peak, active
            active += 1
            peak = max(peak, active)
            try:
                return original(appid, timeout)
            finally:
                active -= 1

        store.fetch_appdetails = counting_fetch
        resolver = MediaResolver(cache, max_concurrency=3, store=store, probe=None)

        async with lock:  # keep the lock object referenced; asyncio needs a running loop
            pass
        await asyncio.gather(*(resolver.get_media({"appid": i, "name": f"G{i}"}) for i in range(1, 25)))

        assert peak <= 3
