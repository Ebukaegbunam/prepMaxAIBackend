"""Unit tests for one_rm library: Epley formula, best-set selection, volume rollup."""
import pytest
from app.lib.one_rm import SetRecord, best_set, epley, total_volume_kg


class TestEpley:
    def test_one_rep_returns_weight(self):
        assert epley(100, 1) == pytest.approx(100 * (1 + 1 / 30), rel=1e-3)

    def test_typical_set(self):
        result = epley(80, 10)
        assert result == round(80 * (1 + 10 / 30), 2)

    def test_higher_reps_means_higher_1rm(self):
        assert epley(80, 12) > epley(80, 8)

    def test_result_rounded_to_two_decimal_places(self):
        result = epley(33, 7)
        assert result == round(result, 2)

    def test_zero_weight(self):
        assert epley(0, 10) == 0.0

    def test_negative_weight_raises(self):
        with pytest.raises(ValueError):
            epley(-10, 5)

    def test_zero_reps_raises(self):
        with pytest.raises(ValueError):
            epley(100, 0)

    def test_reference_value(self):
        # 100 kg × 5 reps → 100 * (1 + 5/30) = 116.67
        assert epley(100, 5) == pytest.approx(116.67, rel=1e-3)


class TestBestSet:
    def test_empty_returns_none(self):
        assert best_set([]) is None

    def test_single_set_returns_it(self):
        s: SetRecord = {"weight_kg": 80.0, "reps": 8, "rpe": 7.0}
        assert best_set([s]) == s

    def test_picks_highest_estimated_1rm(self):
        sets: list[SetRecord] = [
            {"weight_kg": 100.0, "reps": 1, "rpe": 9.0},
            {"weight_kg": 80.0, "reps": 10, "rpe": 8.0},
        ]
        # epley(100, 1) = 103.3; epley(80, 10) = 106.7 → second wins
        result = best_set(sets)
        assert result is not None
        assert result["weight_kg"] == 80.0

    def test_ties_broken_by_weight(self):
        s1: SetRecord = {"weight_kg": 90.0, "reps": 3, "rpe": None}
        s2: SetRecord = {"weight_kg": 80.0, "reps": 3, "rpe": None}
        # same reps, higher weight wins for 1RM and tie-break
        result = best_set([s1, s2])
        assert result is not None
        assert result["weight_kg"] == 90.0


class TestTotalVolumeKg:
    def test_empty_list(self):
        assert total_volume_kg([]) == 0.0

    def test_single_set(self):
        sets: list[SetRecord] = [{"weight_kg": 80.0, "reps": 10, "rpe": None}]
        assert total_volume_kg(sets) == 800.0

    def test_multiple_sets(self):
        sets: list[SetRecord] = [
            {"weight_kg": 80.0, "reps": 10, "rpe": None},
            {"weight_kg": 85.0, "reps": 8, "rpe": None},
            {"weight_kg": 90.0, "reps": 6, "rpe": None},
        ]
        expected = 80 * 10 + 85 * 8 + 90 * 6
        assert total_volume_kg(sets) == pytest.approx(expected, rel=1e-6)

    def test_rounded_to_two_decimals(self):
        sets: list[SetRecord] = [{"weight_kg": 33.33, "reps": 3, "rpe": None}]
        result = total_volume_kg(sets)
        assert result == round(result, 2)
