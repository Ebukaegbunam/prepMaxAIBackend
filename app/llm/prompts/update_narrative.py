"""Prompt for generating/updating the user's third-person profile narrative."""
import json
from typing import Any

VERSION = "v1"

_SYSTEM = """\
You write concise third-person profile paragraphs for competitive bodybuilders.
These paragraphs are used as coaching context by an AI — they must be factual and specific.

Rules:
- 2–4 sentences, third person ("Ebuka is...")
- Draw on the structured fields AND the free-text context
- Never contradict the structured fields
- Capture lifestyle texture and habits that structured fields miss
- Do not add advice, speculation, or encouragement
- Output ONLY the narrative paragraph — no labels, no quotes, no formatting\
"""


def build_messages(
    structured_fields: dict[str, Any],
    free_text: str | None = None,
) -> list[dict[str, str]]:
    user_lines = [
        "Structured profile data:",
        json.dumps(structured_fields, indent=2, default=str),
    ]
    if free_text:
        user_lines += ["", "Additional context from the user:", free_text]
    user_lines += ["", "Write the narrative:"]

    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": "\n".join(user_lines)},
    ]


RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "narrative": {"type": "string"},
    },
    "required": ["narrative"],
    "additionalProperties": False,
}
