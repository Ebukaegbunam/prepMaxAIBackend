"""Prompt for suggesting division-specific workout tweaks as a diff."""
from typing import Any

VERSION = "v1"

_SYSTEM = """\
You are a competitive bodybuilding coach. Given a parsed workout template and the athlete's division, \
suggest specific evidence-based modifications as a structured diff.

Rules:
- Only suggest changes relevant to the division's judging criteria
- Each suggestion must have a clear rationale tied to the division
- Keep suggestions minimal: 1-4 high-impact tweaks
- kind: "add" (add an exercise), "remove" (remove an exercise), "modify" (change sets/reps/exercise)
- Output ONLY valid JSON matching the schema exactly\
"""


def build_messages(
    template: dict[str, Any],
    division: str,
    profile_narrative: str | None = None,
) -> list[dict[str, Any]]:
    import json
    parts = [f"Division: {division}"]
    if profile_narrative:
        parts.append(f"Athlete: {profile_narrative}")
    parts.append(f"Workout template:\n{json.dumps(template, indent=2)}")

    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "kind": {"type": "string", "enum": ["add", "remove", "modify"]},
                    "day_of_week": {"type": "integer"},
                    "exercise_index": {"type": ["integer", "null"]},
                    "before": {"type": ["object", "null"]},
                    "after": {"type": ["object", "null"]},
                    "rationale": {"type": "string"},
                },
                "required": ["id", "kind", "day_of_week", "rationale"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["suggestions"],
    "additionalProperties": False,
}
