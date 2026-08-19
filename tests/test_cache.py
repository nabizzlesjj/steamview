"""Cache TTL, eviction, corruption tolerance and persistence."""

from __future__ import annotations

import json
import os

from steamview.cache import DEFAULT_NEGATIVE_TTL, MediaCache


class TestBasics:
    def test_missing_key_returns_none(self, cache):
        assert cache.get("app:1") is None

    def test_round_trip(self, cache):
        cache.put("app:1", {"key": "app:1", "title": "Hades"})
        assert cache.get("app:1") == {"key": "app:1", "title": "Hades"}

    def test_non_dict_values_are_refused(self, cache):
        cache.put("app:1", "not a dict")
        assert cache.get("app:1") is None

    def test_a_zero_ttl_stores_nothing(self, cache):
        cache.put("app:1", {"a": 1}, ttl=0)
        assert cache.get("app:1") is None

    def test_invalidate_drops_one_entry(self, cache):
        cache.put("app:1", {"a": 1})
        cache.put("app:2", {"a": 2})
        cache.invalidate("app:1")
        assert cache.get("app:1") is None
        assert cache.get("app:2") is not None


class TestTtl:
    def test_entry_survives_until_the_ttl_elapses(self, cache, clock):
        cache.put("app:1", {"a": 1})
        clock.advance(cache.ttl - 1)
        assert cache.get("app:1") == {"a": 1}

    def test_entry_expires_after_the_ttl(self, cache, clock):
        cache.put("app:1", {"a": 1})
        clock.advance(cache.ttl + 1)
        assert cache.get("app:1") is None

    def test_expiry_removes_the_file_from_disk(self, cache, clock):
        cache.put("app:1", {"a": 1})
        clock.advance(cache.ttl + 1)
        cache.get("app:1")
        assert [n for n in os.listdir(cache.directory) if n.endswith(".json")] == []

    def test_failures_use_the_shorter_negative_ttl(self, cache, clock):
        cache.put_failure("app:1", {"source": "empty"})
        clock.advance(DEFAULT_NEGATIVE_TTL + 1)
        assert cache.get("app:1") is None

    def test_a_failure_is_still_served_inside_its_window(self, cache, clock):
        cache.put_failure("app:1", {"source": "empty"})
        clock.advance(DEFAULT_NEGATIVE_TTL - 1)
        assert cache.get("app:1") == {"source": "empty"}


class TestPersistence:
    def test_a_fresh_instance_reads_entries_from_disk(self, tmp_path, clock):
        directory = str(tmp_path / "media")
        MediaCache(directory, clock=clock).put("app:1", {"a": 1})
        assert MediaCache(directory, clock=clock).get("app:1") == {"a": 1}

    def test_disk_expiry_is_honoured_by_a_fresh_instance(self, tmp_path, clock):
        directory = str(tmp_path / "media")
        first = MediaCache(directory, clock=clock)
        first.put("app:1", {"a": 1})
        clock.advance(first.ttl + 1)
        assert MediaCache(directory, clock=clock).get("app:1") is None

    def test_the_memory_layer_answers_without_touching_disk(self, cache):
        cache.put("app:1", {"a": 1})
        for name in os.listdir(cache.directory):
            os.unlink(os.path.join(cache.directory, name))
        assert cache.get("app:1") == {"a": 1}


class TestCorruption:
    def _entry_path(self, cache, key):
        return cache._path(key)  # noqa: SLF001 - deliberate white-box test

    def test_truncated_json_is_discarded(self, cache):
        cache.put("app:1", {"a": 1})
        cache._memory.clear()  # noqa: SLF001
        with open(self._entry_path(cache, "app:1"), "w", encoding="utf-8") as handle:
            handle.write("{not json")
        assert cache.get("app:1") is None

    def test_a_record_missing_its_expiry_is_discarded(self, cache):
        cache.put("app:1", {"a": 1})
        cache._memory.clear()  # noqa: SLF001
        with open(self._entry_path(cache, "app:1"), "w", encoding="utf-8") as handle:
            json.dump({"key": "app:1", "value": {"a": 1}}, handle)
        assert cache.get("app:1") is None

    def test_a_record_whose_value_is_not_a_dict_is_discarded(self, cache):
        cache.put("app:1", {"a": 1})
        cache._memory.clear()  # noqa: SLF001
        with open(self._entry_path(cache, "app:1"), "w", encoding="utf-8") as handle:
            json.dump({"expires_at": 9e18, "value": "junk"}, handle)
        assert cache.get("app:1") is None

    def test_a_corrupt_entry_is_removed_from_disk(self, cache):
        cache.put("app:1", {"a": 1})
        cache._memory.clear()  # noqa: SLF001
        path = self._entry_path(cache, "app:1")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("garbage")
        cache.get("app:1")
        assert not os.path.exists(path)


class TestEviction:
    def test_entries_beyond_the_cap_are_pruned(self, tmp_path, clock):
        cache = MediaCache(str(tmp_path / "media"), max_entries=5, clock=clock)
        for index in range(12):
            clock.advance(1)
            cache.put(f"app:{index}", {"i": index})
        remaining = [n for n in os.listdir(cache.directory) if n.endswith(".json")]
        assert len(remaining) == 5

    def test_the_newest_entry_survives_eviction(self, tmp_path, clock):
        cache = MediaCache(str(tmp_path / "media"), max_entries=3, clock=clock)
        for index in range(10):
            clock.advance(1)
            cache.put(f"app:{index}", {"i": index})
        assert cache.get("app:9") == {"i": 9}

    def test_a_zero_cap_disables_pruning(self, tmp_path, clock):
        cache = MediaCache(str(tmp_path / "media"), max_entries=0, clock=clock)
        for index in range(6):
            cache.put(f"app:{index}", {"i": index})
        assert cache.prune() == 0
        assert len([n for n in os.listdir(cache.directory) if n.endswith(".json")]) == 6


class TestClearAndStats:
    def test_clear_removes_everything_and_reports_the_count(self, cache):
        for index in range(4):
            cache.put(f"app:{index}", {"i": index})
        assert cache.clear() == 4
        assert cache.get("app:0") is None
        assert cache.stats()["entries"] == 0

    def test_clear_on_an_empty_cache_is_a_no_op(self, cache):
        assert cache.clear() == 0

    def test_stats_report_entry_and_byte_counts(self, cache):
        cache.put("app:1", {"key": "app:1"})
        stats = cache.stats()
        assert stats["entries"] == 1
        assert stats["memory_entries"] == 1
        assert stats["bytes"] > 0
        assert stats["directory"] == cache.directory

    def test_stats_survive_a_missing_directory(self, tmp_path, clock):
        cache = MediaCache(str(tmp_path / "media"), clock=clock)
        os.rmdir(cache.directory)
        assert cache.stats()["entries"] == 0

    def test_keys_with_awkward_characters_are_safe_filenames(self, cache):
        key = "shortcut:../../etc/passwd"
        cache.put(key, {"a": 1})
        assert cache.get(key) == {"a": 1}
        assert all("/" not in name for name in os.listdir(cache.directory))
