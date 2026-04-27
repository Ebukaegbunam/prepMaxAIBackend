"""Prompt for estimating macros from a freeform food description."""

VERSION = "v1"

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "calories": {"type": "integer"},
        "protein_g": {"type": "integer"},
        "carbs_g": {"type": "integer"},
        "fat_g": {"type": "integer"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "notes": {"type": "string"},
    },
    "required": ["calories", "protein_g", "carbs_g", "fat_g", "confidence"],
    "additionalProperties": False,
}


def build_messages(description: str) -> list[dict]:
    system = (
        "You are a nutrition database. Estimate the macronutrient content of the described meal "
        "or food. Use standard serving sizes and published nutrition data. "
        "Be honest about confidence level."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Estimate macros for: {description}"},
    ]
