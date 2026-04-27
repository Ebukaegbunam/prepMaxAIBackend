"""Calorie and macro target calculator.

Mifflin-St Jeor BMR, TDEE by training days, and phase-aware deficit ramp.
"""
from typing import TypedDict


class MacroTargets(TypedDict):
    calories: int
    protein_g: int
    carbs_g: int
    fat_g: int


_ACTIVITY_MULTIPLIERS = {
    0: 1.2,
    1: 1.2,
    2: 1.375,
    3: 1.55,
    4: 1.55,
    5: 1.55,
    6: 1.725,
    7: 1.725,
}


def bmr(weight_kg: float, height_cm: float, age: int, sex: str) -> float:
    """Mifflin-St Jeor BMR in kcal/day."""
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + 5 if sex.lower() in ("male", "m") else base - 161


def tdee(bmr_kcal: float, training_days: int) -> float:
    """Total daily energy expenditure using training days per week as activity proxy."""
    multiplier = _ACTIVITY_MULTIPLIERS.get(min(training_days, 7), 1.55)
    return bmr_kcal * multiplier


def targets_for_week(
    prep_length_weeks: int,
    week_number: int,
    maintenance_weeks: int,
    tdee_kcal: float,
    weight_kg: float,
) -> MacroTargets:
    """Compute daily macro targets for a given week of prep.

    Maintenance phase: TDEE, no deficit.
    Cut phase: deficit ramps linearly from 250 to 500 kcal/day.
    Protein: 2.2g/kg, fat: 0.9g/kg, carbs: fill remaining calories.
    """
    if week_number < 1:
        raise ValueError("week_number must be >= 1")

    in_cut = week_number > maintenance_weeks
    if in_cut:
        cut_week = week_number - maintenance_weeks
        cut_total_weeks = max(prep_length_weeks - maintenance_weeks, 1)
        progress = (cut_week - 1) / max(cut_total_weeks - 1, 1)
        deficit = 250 + progress * 250
        calories = max(round(tdee_kcal - deficit), 1200)
    else:
        calories = round(tdee_kcal)

    protein_g = round(weight_kg * 2.2)
    fat_g = round(weight_kg * 0.9)
    protein_cal = protein_g * 4
    fat_cal = fat_g * 9
    carbs_cal = max(calories - protein_cal - fat_cal, 0)
    carbs_g = round(carbs_cal / 4)

    return MacroTargets(calories=calories, protein_g=protein_g, carbs_g=carbs_g, fat_g=fat_g)
