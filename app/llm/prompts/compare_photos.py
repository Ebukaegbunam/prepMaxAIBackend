"""Prompt for AI body-part photo comparison."""

VERSION = "v1"

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "changes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "area": {"type": "string"},
                    "observation": {"type": "string"},
                    "direction": {"type": "string", "enum": ["improved", "declined", "unchanged", "unclear"]},
                },
                "required": ["area", "observation", "direction"],
                "additionalProperties": False,
            },
        },
        "recommendations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "changes", "recommendations"],
    "additionalProperties": False,
}


def build_messages(body_part: str | None, image_a_b64: str, image_b_b64: str) -> list[dict]:
    system = (
        "You are a bodybuilding physique coach. Compare two progress photos and provide "
        "an objective, specific, encouraging analysis of changes. "
        "Do not make medical claims. Focus on visible physique changes."
    )
    label = f" focusing on {body_part}" if body_part else ""
    user_content = [
        {"type": "text", "text": f"Compare these two progress photos{label}. "
         "Photo A is the earlier photo, Photo B is the more recent."},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_a_b64}"}},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b_b64}"}},
    ]
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]
