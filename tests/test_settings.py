"""Settings validation, clamping and persistence."""

from __future__ import annotations

import json
import os

import pytest

from steamview.settings import DEFAULTS, POSITIONS, PREVIEW_MODES, SIZES, SettingsStore, validate


class TestValidate:
    @pytest.mark.parametrize("raw", [None, {}, "junk", 42, [], {"unknown_key": True}])
    def test_unusable_input_yields_the_defaults(self, raw):
        assert validate(raw) == DEFAULTS

    def test_unknown_keys_are_dropped(self):
        assert "unknown_key" not in validate({"unknown_key": "x"})

    def test_every_default_key_is_always_present(self):
        assert set(validate({"enabled": False})) == set(DEFAULTS)

    @pytest.mark.parametrize(("raw", "expected"), [("true", True), ("off", False), (1, True), (0, False)])
    def test_booleans_are_coerced_from_loose_values(self, raw, expected):
        assert validate({"enabled": raw})["enabled"] is expected

    def test_an_uninterpretable_boolean_falls_back_to_the_default(self):
        assert validate({"enabled": "maybe"})["enabled"] is DEFAULTS["enabled"]

    @pytest.mark.parametrize("mode", PREVIEW_MODES)
    def test_every_preview_mode_is_accepted(self, mode):
        assert validate({"preview_mode": mode})["preview_mode"] == mode

    def test_preview_mode_is_case_insensitive(self):
        assert validate({"preview_mode": "  SCREENSHOTS "})["preview_mode"] == "screenshots"

    def test_an_unknown_preview_mode_falls_back(self):
        assert validate({"preview_mode": "hologram"})["preview_mode"] == DEFAULTS["preview_mode"]

    @pytest.mark.parametrize("position", POSITIONS)
    def test_every_position_is_accepted(self, position):
        assert validate({"position": position})["position"] == position

    @pytest.mark.parametrize("size", SIZES)
    def test_every_size_is_accepted(self, size):
        assert validate({"size": size})["size"] == size

    @pytest.mark.parametrize(("raw", "expected"), [(-500, 0), (999999, 5000), (1200, 1200), ("800", 800)])
    def test_autoplay_delay_is_clamped(self, raw, expected):
        assert validate({"autoplay_delay_ms": raw})["autoplay_delay_ms"] == expected

    @pytest.mark.parametrize("raw", ["soon", None, {}, True])
    def test_an_uninterpretable_delay_falls_back(self, raw):
        assert validate({"autoplay_delay_ms": raw})["autoplay_delay_ms"] == DEFAULTS["autoplay_delay_ms"]

    def test_validation_is_idempotent(self):
        once = validate({"size": "l", "autoplay_delay_ms": 99999})
        assert validate(once) == once


class TestStore:
    def test_a_missing_file_loads_the_defaults(self, tmp_path):
        assert SettingsStore(str(tmp_path)).load() == DEFAULTS

    def test_update_persists_to_disk(self, tmp_path):
        SettingsStore(str(tmp_path)).update({"size": "l", "enabled": False})
        assert SettingsStore(str(tmp_path)).load()["size"] == "l"

    def test_update_merges_rather_than_replaces(self, tmp_path):
        store = SettingsStore(str(tmp_path))
        store.update({"size": "l"})
        result = store.update({"muted": False})
        assert result["size"] == "l"
        assert result["muted"] is False

    def test_update_clamps_before_persisting(self, tmp_path):
        SettingsStore(str(tmp_path)).update({"autoplay_delay_ms": 10**9})
        assert SettingsStore(str(tmp_path)).load()["autoplay_delay_ms"] == 5000

    @pytest.mark.parametrize("patch", [None, "junk", 42, []])
    def test_a_non_dict_patch_is_ignored(self, tmp_path, patch):
        store = SettingsStore(str(tmp_path))
        store.update({"size": "l"})
        assert store.update(patch)["size"] == "l"

    def test_corrupt_json_falls_back_to_the_defaults(self, tmp_path):
        store = SettingsStore(str(tmp_path))
        with open(store.path, "w", encoding="utf-8") as handle:
            handle.write("{oh no")
        assert store.load() == DEFAULTS

    def test_hand_edited_out_of_range_values_are_repaired(self, tmp_path):
        store = SettingsStore(str(tmp_path))
        with open(store.path, "w", encoding="utf-8") as handle:
            json.dump({"size": "enormous", "autoplay_delay_ms": -3, "preview_mode": "hologram"}, handle)
        loaded = store.load()
        assert loaded["size"] == DEFAULTS["size"]
        assert loaded["autoplay_delay_ms"] == 0
        assert loaded["preview_mode"] == DEFAULTS["preview_mode"]

    def test_reset_restores_the_defaults_on_disk(self, tmp_path):
        store = SettingsStore(str(tmp_path))
        store.update({"enabled": False, "size": "s"})
        assert store.reset() == DEFAULTS
        assert SettingsStore(str(tmp_path)).load() == DEFAULTS

    def test_get_loads_lazily_on_first_call(self, tmp_path):
        SettingsStore(str(tmp_path)).update({"size": "s"})
        assert SettingsStore(str(tmp_path)).get()["size"] == "s"

    def test_an_unwritable_directory_does_not_raise(self, tmp_path):
        store = SettingsStore(str(tmp_path / "settings"))
        os.makedirs(tmp_path / "settings", exist_ok=True)
        os.chmod(tmp_path / "settings", 0o500)
        try:
            assert store.update({"size": "l"})["size"] == "l"
        finally:
            os.chmod(tmp_path / "settings", 0o700)

    def test_no_temp_file_is_left_behind(self, tmp_path):
        store = SettingsStore(str(tmp_path))
        store.update({"size": "l"})
        assert not any(name.endswith(".tmp") for name in os.listdir(tmp_path))
