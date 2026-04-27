"""Prompt for generating a full week of meal plans."""

VERSION = "v1"

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "days": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "day_of_week": {"type": "integer"},
                    "slots": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["day_of_week", "slots"],
                "additionalProperties": False,
            },
        },
        "reasoning": {"type": "string"},
    },
    "required": ["days", "reasoning"],
    "additionalProperties": False,
}


def build_messages(
    targets: dict,
    profile_narrative: str | None,
    dietary_restrictions: list[str],
    schedule_hint: str | None,
    pantry: list[str],
    vary_by: str | None,
) -> list[dict]:
    system = (
        "You are a bodybuilding nutrition coach. Create a complete 7-day meal plan "
        "that hits the macro targets each day. Vary meals across the week for adherence. "
        "Batch-cook friendly options are preferred for prep ease."
    )
    parts = [
        f"Daily targets: {targets['calories']} kcal, "
        f"{targets['protein_g']}g protein, {targets['carbs_g']}g carbs, {targets['fat_g']}g fat.",
    ]
    if profile_narrative:
        parts.append(f"\nAthlete context:\n{profile_narrative}")
    if dietary_restrictions:
        parts.append(f"\nDietary restrictions: {', '.join(dietary_restrictions)}")
    if schedule_hint:
        parts.append(f"\nWeekly schedule: {schedule_hint}")
    if pantry:
        parts.append(f"\nAvailable foods: {', '.join(pantry)}")
    if vary_by:
        parts.append(f"\nVariation strategy: {vary_by}")
    parts.append("\nReturn 7 days of meal plans, one per day_of_week (1=Monday).")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n".join(parts)},
    ]
