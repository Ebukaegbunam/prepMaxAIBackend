"""Prompt for generating a weekly plan summary with macro targets per week."""

VERSION = "v1"

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "weeks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "week_number": {"type": "integer"},
                    "phase": {"type": "string", "enum": ["maintenance", "cut"]},
                    "targets": {
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
                "required": ["week_number", "phase", "targets"],
                "additionalProperties": False,
            },
        },
        "reasoning": {"type": "string"},
    },
    "required": ["weeks", "reasoning"],
    "additionalProperties": False,
}


def build_messages(
    profile_narrative: str | None,
    prep_length_weeks: int,
    maintenance_weeks: int,
    week_targets: list[dict],
) -> list[dict]:
    system = (
        "You are a bodybuilding nutrition expert. "
        "Given a prep schedule and computed macro targets, provide a weekly breakdown "
        "with brief coaching notes for each week."
    )
    user_parts = []
    if profile_narrative:
        user_parts.append(f"Athlete profile:\n{profile_narrative}\n")
    user_parts.append(
        f"Prep: {prep_length_weeks} weeks total — {maintenance_weeks} maintenance, "
        f"{prep_length_weeks - maintenance_weeks} cut.\n"
    )
    user_parts.append("Computed targets per week:\n")
    for t in week_targets:
        user_parts.append(
            f"  Week {t['week_number']} ({t['phase']}): "
            f"{t['targets']['calories']} kcal, "
            f"{t['targets']['protein_g']}g protein, "
            f"{t['targets']['carbs_g']}g carbs, "
            f"{t['targets']['fat_g']}g fat"
        )
    user_parts.append("\nReturn the structured weekly plan with coaching notes.")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n".join(user_parts)},
    ]
