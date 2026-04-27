"""Prompt for parsing a natural-language workout plan into structured template."""
from typing import Any

VERSION = "v1"

_SYSTEM = """\
You parse natural-language workout descriptions into structured JSON templates for bodybuilders.

Rules:
- Preserve every exercise mentioned; do not add or remove
- day_of_week: 1=Monday through 7=Sunday; infer from context ("Monday", "Day 1", etc.)
- target_reps: use the string exactly as given (e.g. "8-10", "AMRAP", "12")
- raw_name: the exercise name exactly as the user wrote it
- Output ONLY valid JSON matching the schema exactly\
"""


def build_messages(
    text: str,
    division: str | None = None,
    profile_narrative: str | None = None,
) -> list[dict[str, Any]]:
    context_parts = []
    if division:
        context_parts.append(f"Division: {division}")
    if profile_narrative:
        context_parts.append(f"Athlete profile: {profile_narrative}")

    context = "\n".join(context_parts)
    user_content = (f"{context}\n\n" if context else "") + f"Workout plan:\n{text}"

    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": user_content},
    ]


RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "days": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "day_of_week": {"type": "integer", "minimum": 1, "maximum": 7},
                    "title": {"type": "string"},
                    "exercises": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "order": {"type": "integer"},
                                "raw_name": {"type": "string"},
                                "target_sets": {"type": ["integer", "null"]},
                                "target_reps": {"type": ["string", "null"]},
                                "rest_seconds": {"type": ["integer", "null"]},
                                "notes": {"type": ["string", "null"]},
                            },
                            "required": ["order", "raw_name"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["day_of_week", "title", "exercises"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["name", "days"],
    "additionalProperties": False,
}
