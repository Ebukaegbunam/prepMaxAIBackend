"""Epley estimated one-rep max formula: 1RM = weight * (1 + reps / 30)."""

from typing import TypedDict


def epley(weight_kg: float, reps: int) -> float:
    """Return estimated 1RM in kg. Returns weight unchanged for 1 rep."""
    if reps <= 0:
        raise ValueError("reps must be positive")
    if weight_kg < 0:
        raise ValueError("weight_kg must be non-negative")
    return round(weight_kg * (1 + reps / 30), 2)


class SetRecord(TypedDict):
    weight_kg: float
    reps: int
    rpe: float | None


def best_set(sets: list[SetRecord]) -> SetRecord | None:
    """Return set with highest estimated 1RM; ties broken by weight, then reps."""
    if not sets:
        return None
    return max(
        sets,
        key=lambda s: (epley(s["weight_kg"], s["reps"]), s["weight_kg"], s["reps"]),
    )


def total_volume_kg(sets: list[SetRecord]) -> float:
    """Sum of weight_kg * reps across all sets."""
    return round(sum(s["weight_kg"] * s["reps"] for s in sets), 2)
