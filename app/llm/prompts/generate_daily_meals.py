"""Prompt for generating a daily meal plan within macro targets."""

VERSION = "v1"

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "slots": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "slot": {"type": "string"},
                    "name": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "food": {"type": "string"},
                                "quantity": {"type": "string"},
                                "unit": {"type": "string"},
                            },
                            "required": ["food", "quantity", "unit"],
                            "additionalProperties": False,
                        },
                    },
                    "macros": {
                        "type": "object",
                        "properties": {
                            "calories": {"type": "integer"},
                            "protein_g": {"type": "integer"},
                            "carbs_g": {"type": "integer"},
                            "fat_g": {"type": "integer"},
                        },
                        "required": ["calories", "protein_g", "carbs_g", "fat_g"],
                        "additionalProperties": False,
                    },
                    "notes": {"type": "string"},
                },
                "required": ["slot", "name", "items", "macros"],
                "additionalProperties": False,
            },
        },
        "reasoning": {"type": "string"},
    },
    "required": ["slots", "reasoning"],
    "additionalProperties": False,
}


def build_messages(
    targets: dict,
    profile_narrative: str | None,
    dietary_restrictions: list[str],
    schedule_hint: str | None,
    pantry: list[str],
) -> list[dict]:
    system = (
        "You are a bodybuilding nutrition coach. Create a practical daily meal plan "
        "that exactly meets the given macro targets. Use whole foods. Distribute meals "
        "across the day based on the schedule hint if provided."
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
        parts.append(f"\nSchedule: {schedule_hint}")
    if pantry:
        parts.append(f"\nAvailable foods: {', '.join(pantry)}")
    parts.append("\nReturn a complete meal plan for the day.")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n".join(parts)},
    ]
