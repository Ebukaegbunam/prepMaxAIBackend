"""Unit tests for calorie_engine: Mifflin-St Jeor BMR, TDEE, macro targets."""
import pytest
from app.lib.calorie_engine import MacroTargets, bmr, tdee, targets_for_week


class TestBMR:
    def test_male_reference(self):
        # 80 kg, 175 cm, 25 years, male
        # 10*80 + 6.25*175 - 5*25 + 5 = 800 + 1093.75 - 125 + 5 = 1773.75
        result = bmr(80, 175, 25, "male")
        assert result == pytest.approx(1773.75, rel=1e-4)

    def test_female_reference(self):
        # 60 kg, 165 cm, 30 years, female
        # 10*60 + 6.25*165 - 5*30 - 161 = 600 + 1031.25 - 150 - 161 = 1320.25
        result = bmr(60, 165, 30, "female")
        assert result == pytest.approx(1320.25, rel=1e-4)

    def test_sex_case_insensitive(self):
        assert bmr(80, 175, 25, "Male") == bmr(80, 175, 25, "male")
        assert bmr(80, 175, 25, "m") == bmr(80, 175, 25, "male")

    def test_female_lower_than_male_same_stats(self):
        m = bmr(80, 175, 25, "male")
        f = bmr(80, 175, 25, "female")
        assert m > f
        assert m - f == pytest.approx(166, rel=1e-3)  # 5 - (-161)


class TestTDEE:
    def test_sedentary(self):
        result = tdee(1773.75, 0)
        assert result == pytest.approx(1773.75 * 1.2, rel=1e-4)

    def test_moderate_3_days(self):
        result = tdee(1773.75, 3)
        assert result == pytest.approx(1773.75 * 1.55, rel=1e-4)

    def test_active_6_days(self):
        result = tdee(1773.75, 6)
        assert result == pytest.approx(1773.75 * 1.725, rel=1e-4)

    def test_7_days_same_as_6(self):
        assert tdee(1500, 7) == tdee(1500, 6)

    def test_2_days(self):
        result = tdee(1500, 2)
        assert result == pytest.approx(1500 * 1.375, rel=1e-4)


class TestTargetsForWeek:
    def _base_tdee(self) -> float:
        return tdee(bmr(80, 175, 25, "male"), 5)

    def test_maintenance_week_no_deficit(self):
        tdee_val = self._base_tdee()
        targets = targets_for_week(16, 1, 4, tdee_val, 80)
        assert targets["calories"] == round(tdee_val)

    def test_first_cut_week_250_deficit(self):
        tdee_val = self._base_tdee()
        targets = targets_for_week(16, 5, 4, tdee_val, 80)
        assert targets["calories"] == pytest.approx(round(tdee_val) - 250, abs=1)

    def test_last_cut_week_500_deficit(self):
        tdee_val = self._base_tdee()
        targets = targets_for_week(16, 16, 4, tdee_val, 80)
        assert targets["calories"] == pytest.approx(round(tdee_val) - 500, abs=1)

    def test_protein_is_2pt2_per_kg(self):
        targets = targets_for_week(16, 1, 4, 2750, 80)
        assert targets["protein_g"] == round(80 * 2.2)

    def test_fat_is_0pt9_per_kg(self):
        targets = targets_for_week(16, 1, 4, 2750, 80)
        assert targets["fat_g"] == round(80 * 0.9)

    def test_carbs_fill_remainder(self):
        targets = targets_for_week(16, 1, 4, 2750, 80)
        protein_cal = targets["protein_g"] * 4
        fat_cal = targets["fat_g"] * 9
        carbs_cal = targets["calories"] - protein_cal - fat_cal
        assert targets["carbs_g"] == round(carbs_cal / 4)

    def test_calories_never_below_1200(self):
        targets = targets_for_week(16, 16, 4, 1300, 50)
        assert targets["calories"] >= 1200

    def test_invalid_week_number_raises(self):
        with pytest.raises(ValueError):
            targets_for_week(16, 0, 4, 2750, 80)

    def test_all_16_weeks_produce_valid_targets(self):
        tdee_val = self._base_tdee()
        for w in range(1, 17):
            t = targets_for_week(16, w, 4, tdee_val, 80)
            assert t["calories"] > 0
            assert t["protein_g"] > 0
            assert t["fat_g"] > 0
            assert t["carbs_g"] >= 0

    def test_deficit_increases_across_cut(self):
        tdee_val = self._base_tdee()
        week5_cal = targets_for_week(16, 5, 4, tdee_val, 80)["calories"]
        week16_cal = targets_for_week(16, 16, 4, tdee_val, 80)["calories"]
        assert week5_cal > week16_cal
