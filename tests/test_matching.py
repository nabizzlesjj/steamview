"""Shortcut-name to store-appid ranking.

The bar here is deliberately asymmetric: a missed match costs a trailer,
a wrong match shows the wrong game.
"""

from __future__ import annotations

import pytest

from steamview.matching import (
    CONFIDENT_THRESHOLD,
    normalize_for_match,
    pick_best,
    rank_candidates,
    score_titles,
    search_terms,
    strip_edition_suffix,
    strip_store_suffix,
)


class TestNormalize:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Hades™", "hades"),
            ("Baldur's Gate 3", "baldurs gate 3"),
            ("Baldur’s Gate 3", "baldurs gate 3"),
            ("  DOOM   Eternal  ", "doom eternal"),
            ("The Witcher 3: Wild Hunt", "the witcher 3 wild hunt"),
            ("", ""),
        ],
    )
    def test_normalisation(self, raw, expected):
        assert normalize_for_match(raw) == expected

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Final Fantasy VII", "final fantasy 7"),
            ("Grand Theft Auto IV", "grand theft auto 4"),
            ("Civilization VI", "civilization 6"),
        ],
    )
    def test_multi_character_roman_numerals_become_digits(self, raw, expected):
        assert normalize_for_match(raw) == expected

    @pytest.mark.parametrize("raw", ["Mega Man X", "I Am Bread", "Project V"])
    def test_single_letters_are_left_alone(self, raw):
        # "I", "V" and "X" are ordinary words often enough that rewriting
        # them would invent matches.
        assert normalize_for_match(raw) == raw.lower()


class TestSuffixStripping:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Cyberpunk 2077 (Epic)", "Cyberpunk 2077"),
            ("Hades [GOG]", "Hades"),
            ("Control - Ubisoft Connect", "Control"),
            ("Fallout 3 (Amazon Games)", "Fallout 3"),
            ("Forza Horizon 5 (Xbox Cloud Gaming)", "Forza Horizon 5"),
            ("Halo Infinite - Xbox", "Halo Infinite"),
            ("Plain Title", "Plain Title"),
        ],
    )
    def test_store_suffixes(self, raw, expected):
        assert strip_store_suffix(raw) == expected

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("DOOM Eternal - Deluxe Edition", "DOOM Eternal"),
            ("Skyrim: Special Edition", "Skyrim"),
            ("The Witcher 3 (Game of the Year Edition)", "The Witcher 3"),
            ("Dark Souls Remastered", "Dark Souls"),
            ("Plain Title", "Plain Title"),
        ],
    )
    def test_edition_suffixes(self, raw, expected):
        assert strip_edition_suffix(raw) == expected

    def test_stacked_suffixes_are_stripped_together(self):
        assert strip_edition_suffix(strip_store_suffix("DOOM Eternal - Deluxe Edition (Epic)")) == "DOOM Eternal"


class TestSearchTerms:
    def test_most_specific_term_comes_first(self):
        assert search_terms("DOOM Eternal - Deluxe Edition (Epic)") == [
            "DOOM Eternal - Deluxe Edition (Epic)",
            "DOOM Eternal - Deluxe Edition",
            "DOOM Eternal",
        ]

    def test_undecorated_name_yields_a_single_term(self):
        assert search_terms("Hades") == ["Hades"]

    def test_blank_name_yields_nothing(self):
        assert search_terms("   ") == []


class TestScoring:
    @pytest.mark.parametrize(
        ("query", "candidate"),
        [
            ("Cyberpunk 2077 (Epic)", "Cyberpunk 2077"),
            ("Hades™", "Hades"),
            ("Baldur's Gate 3", "Baldurs Gate 3"),
            ("DOOM Eternal - Deluxe Edition", "DOOM Eternal"),
            ("The Witcher 3: Wild Hunt", "The Witcher 3: Wild Hunt - Game of the Year Edition"),
            ("FINAL FANTASY VII", "Final Fantasy VII"),
        ],
    )
    def test_same_game_clears_the_threshold(self, query, candidate):
        assert score_titles(query, candidate) >= CONFIDENT_THRESHOLD

    @pytest.mark.parametrize(
        ("query", "candidate"),
        [
            ("Portal", "Portal 2"),
            ("Grand Theft Auto V", "Grand Theft Auto IV"),
            ("Final Fantasy VII", "Final Fantasy VIII"),
            ("Dead Cells", "Dead Space"),
            ("Hades", "Hades II"),
            ("Some Obscure Indie", "Totally Different Game"),
        ],
    )
    def test_different_games_stay_below_the_threshold(self, query, candidate):
        assert score_titles(query, candidate) < CONFIDENT_THRESHOLD

    def test_identical_titles_score_one(self):
        assert score_titles("Hades", "Hades") == 1.0

    @pytest.mark.parametrize(("query", "candidate"), [("", "Hades"), ("Hades", ""), ("", "")])
    def test_empty_input_scores_zero(self, query, candidate):
        assert score_titles(query, candidate) == 0.0


class TestRanking:
    def test_best_match_sorts_first_regardless_of_input_order(self):
        items = [
            {"id": 611670, "name": "Cyberpunk 2077 Phantom Liberty"},
            {"id": 1091500, "name": "Cyberpunk 2077"},
        ]
        ranked = rank_candidates("Cyberpunk 2077 (Epic)", items)
        assert ranked[0][0] == 1091500

    def test_ties_break_toward_steams_own_ordering(self):
        items = [{"id": 1, "name": "Hades"}, {"id": 2, "name": "Hades"}]
        assert rank_candidates("Hades", items)[0][0] == 1

    @pytest.mark.parametrize(
        "junk",
        [
            [{"id": 0, "name": "Zero"}],
            [{"id": "abc", "name": "Bad id"}],
            [{"name": "No id"}],
            [{"id": 5, "name": ""}],
            ["not a dict", None, 42],
        ],
    )
    def test_malformed_items_are_skipped(self, junk):
        assert rank_candidates("Hades", junk) == []

    def test_none_and_empty_iterables_are_safe(self):
        assert rank_candidates("Hades", None) == []
        assert rank_candidates("Hades", []) == []


class TestPickBest:
    def test_confident_match_is_returned(self):
        best = pick_best("Cyberpunk 2077 (Epic)", [{"id": 1091500, "name": "Cyberpunk 2077"}])
        assert best is not None
        assert best[0] == 1091500

    def test_unconfident_match_is_rejected(self):
        assert pick_best("Portal", [{"id": 620, "name": "Portal 2"}]) is None

    def test_no_candidates_returns_none(self):
        assert pick_best("Hades", []) is None

    def test_threshold_is_overridable(self):
        assert pick_best("Portal", [{"id": 620, "name": "Portal 2"}], threshold=0.1) is not None
