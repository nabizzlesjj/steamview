"""Settings validation, clamping and persistence."""

from __future__ import annotations

import json
import os

import pytest

from steamview.settings import (
    DEFAULTS,
    POSITIONS,
    PREVIEW_MODES,
    SIZES,
    TRIGGERS,
    SettingsStore,
    validate,
)


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

    def test_the_preview_appears_automatically_by_default(self):
        """Upgrading must not silently switch anyone to the View button."""
        assert DEFAULTS["trigger"] == "auto"

    @pytest.mark.parametrize("trigger", TRIGGERS)
    def test_every_trigger_is_accepted(self, trigger):
        assert validate({"trigger": trigger})["trigger"] == trigger

    @pytest.mark.parametrize("raw", ["view", "VIEW BUTTON", "", None, 9, True])
    def test_an_unknown_trigger_falls_back_to_auto(self, raw):
        assert validate({"trigger": raw})["trigger"] == "auto"

    def test_the_preview_button_defaults_to_what_a_deck_sends(self):
        """35: a Deck's View button as measured, not the published 9."""
        assert DEFAULTS["preview_button"] == 35
        assert DEFAULTS["preview_button_captured"] is False

    def test_an_uncaptured_9_from_1_3_moves_to_the_new_default(self):
        """1.3.0/1.3.1 wrote their default, 9, for anyone who changed any setting."""
        stored = {"trigger": "view_button", "preview_button": 9}
        assert validate(stored)["preview_button"] == 35

    def test_any_uncaptured_value_follows_the_default(self):
        for raw in (9, 20, 0, "35", None):
            assert validate({"preview_button": raw})["preview_button"] == 35

    @pytest.mark.parametrize(("raw", "expected"), [(35, 35), (9, 9), ("20", 20), (0, 0), (255, 255)])
    def test_a_captured_button_is_kept(self, raw, expected):
        """Including 9: someone on an older Steam may really have captured it."""
        result = validate({"preview_button": raw, "preview_button_captured": True})
        assert result["preview_button"] == expected
        assert result["preview_button_captured"] is True

    @pytest.mark.parametrize(("raw", "expected"), [(-1, 0), (999, 255)])
    def test_an_out_of_range_capture_is_clamped(self, raw, expected):
        result = validate({"preview_button": raw, "preview_button_captured": True})
        assert result["preview_button"] == expected

    @pytest.mark.parametrize("raw", ["view", None, True, [], 1.5j])
    def test_an_unusable_capture_falls_back_to_the_default(self, raw):
        result = validate({"preview_button": raw, "preview_button_captured": True})
        assert result["preview_button"] == 35

    def test_a_capture_survives_a_save_and_reload(self, tmp_path):
        store = SettingsStore(str(tmp_path))
        store.update({"preview_button": 20, "preview_button_captured": True})
        assert SettingsStore(str(tmp_path)).load()["preview_button"] == 20

    def test_a_settings_file_from_before_triggers_existed_still_loads(self):
        older = {key: value for key, value in DEFAULTS.items() if key != "trigger"}
        assert validate(older)["trigger"] == "auto"

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


class TestPreviewDelay:
    """Separate from the autoplay delay: this one gates the overlay
    appearing at all, so it applies in screenshots-only mode too."""

    def test_it_has_a_default(self):
        assert DEFAULTS["preview_delay_ms"] == 300

    @pytest.mark.parametrize(("raw", "expected"), [(-100, 0), (99999, 3000), (0, 0), (1500, 1500), ("800", 800)])
    def test_it_is_clamped(self, raw, expected):
        assert validate({"preview_delay_ms": raw})["preview_delay_ms"] == expected

    @pytest.mark.parametrize("raw", ["soon", None, {}, True, []])
    def test_an_uninterpretable_value_falls_back(self, raw):
        assert validate({"preview_delay_ms": raw})["preview_delay_ms"] == DEFAULTS["preview_delay_ms"]

    def test_it_is_independent_of_the_autoplay_delay(self):
        result = validate({"preview_delay_ms": 0, "autoplay_delay_ms": 5000})
        assert result["preview_delay_ms"] == 0
        assert result["autoplay_delay_ms"] == 5000

    def test_it_persists(self, tmp_path):
        SettingsStore(str(tmp_path)).update({"preview_delay_ms": 1200})
        assert SettingsStore(str(tmp_path)).load()["preview_delay_ms"] == 1200

    def test_an_older_settings_file_without_it_gets_the_default(self, tmp_path):
        store = SettingsStore(str(tmp_path))
        with open(store.path, "w", encoding="utf-8") as handle:
            json.dump({"enabled": True, "preview_mode": "trailer", "size": "l"}, handle)
        loaded = store.load()
        assert loaded["preview_delay_ms"] == DEFAULTS["preview_delay_ms"]
        assert loaded["size"] == "l"
