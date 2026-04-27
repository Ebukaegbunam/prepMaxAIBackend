"""Prompt for AI weekly prep report."""

VERSION = "v1"

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "weight_analysis": {"type": "string"},
        "training_analysis": {"type": "string"},
        "nutrition_analysis": {"type": "string"},
        "wins": {"type": "array", "items": {"type": "string"}},
        "focus_next_week": {"type": "array", "items": {"type": "string"}},
        "overall_trajectory": {"type": "string", "enum": ["on_track", "ahead", "behind", "needs_attention"]},
    },
    "required": ["headline", "weight_analysis", "training_analysis", "nutrition_analysis", "wins", "focus_next_week", "overall_trajectory"],
    "additionalProperties": False,
}


def build_messages(
    week_number: int,
    prep_length_weeks: int,
    weight_logs: list[dict],
    meal_log_totals: list[dict],
    session_count: int,
    check_in: dict | None,
    prior_report: dict | None,
    profile_narrative: str | None,
) -> list[dict]:
    system = (
        "You are a bodybuilding prep coach. Write a concise, data-driven weekly check-in report. "
        "Be direct, specific, and encouraging. Reference actual numbers from the week's data."
    )
    parts = [f"Week {week_number} of {prep_length_weeks} prep report."]
    if profile_narrative:
        parts.append(f"\nAthlete profile: {profile_narrative[:300]}")
    if weight_logs:
        weights = [w["weight_kg"] for w in weight_logs]
        parts.append(f"\nWeight logs this week: {weights} kg")
    if meal_log_totals:
        avg_cal = sum(d.get("calories", 0) for d in meal_log_totals) / max(len(meal_log_totals), 1)
        parts.append(f"\nAvg daily calories logged: {round(avg_cal)}")
    parts.append(f"\nTraining sessions logged: {session_count}")
    if check_in:
        parts.append(f"\nCheck-in mood: {check_in.get('mood')}/5, energy: {check_in.get('energy')}/5")
    if prior_report:
        parts.append(f"\nPrior week trajectory: {prior_report.get('overall_trajectory', 'unknown')}")
    parts.append("\nWrite a complete weekly report.")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n".join(parts)},
    ]
