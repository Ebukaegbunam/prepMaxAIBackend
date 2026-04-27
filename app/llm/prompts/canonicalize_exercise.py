"""Prompt for LLM-based exercise name canonicalization."""
from typing import Any

VERSION = "v1"

_SYSTEM = """\
You are an exercise name normalizer. Given a free-text exercise name and a list of canonical exercise names, \
return the best match or null if none fits.

Rules:
- Match on meaning, not just spelling (e.g. "incline DB press" → "Incline Dumbbell Bench Press")
- Only return a match if you are confident (>80% sure)
- Return exactly the canonical name string as given in the list, or null
- Do not invent names not in the list
- Output ONLY valid JSON: {"canonical_name": "<name>" | null, "confidence": "high" | "medium" | "low"}\
"""


def build_messages(raw_name: str, canonical_names: list[str]) -> list[dict[str, Any]]:
    name_list = "\n".join(f"- {n}" for n in canonical_names)
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": f'Exercise to match: "{raw_name}"\n\nCanonical names:\n{name_list}'},
    ]


RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "canonical_name": {"type": ["string", "null"]},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["canonical_name", "confidence"],
    "additionalProperties": False,
}
