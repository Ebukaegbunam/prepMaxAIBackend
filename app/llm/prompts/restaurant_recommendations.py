"""Prompt for generating restaurant order recommendations with macro estimates."""

VERSION = "v1"

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "place_id": {"type": "string"},
                    "name": {"type": "string"},
                    "address": {"type": "string"},
                    "suggested_orders": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "estimated_macros": {
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
                                "fit_score": {"type": "string", "enum": ["great", "good", "ok", "poor"]},
                            },
                            "required": ["name", "estimated_macros", "fit_score"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["place_id", "name", "suggested_orders"],
                "additionalProperties": False,
            },
        },
        "reasoning": {"type": "string"},
    },
    "required": ["results", "reasoning"],
    "additionalProperties": False,
}


def build_messages(
    restaurants: list[dict],
    remaining_macros: dict,
    filter_hint: str | None,
) -> list[dict]:
    system = (
        "You are a bodybuilding nutrition coach. For each restaurant, suggest the best "
        "order options that fit within the remaining macro budget. Prioritize high-protein, "
        "low-fat options. Score each suggestion."
    )
    parts = [
        f"Remaining macros: {remaining_macros['calories']} kcal, "
        f"{remaining_macros['protein_g']}g protein, "
        f"{remaining_macros['carbs_g']}g carbs, {remaining_macros['fat_g']}g fat.",
    ]
    if filter_hint:
        parts.append(f"\nDietary preference: {filter_hint}")
    parts.append("\nRestaurants nearby:")
    for r in restaurants:
        parts.append(f"  - {r['name']} (ID: {r['place_id']}, address: {r.get('address', 'unknown')})")
    parts.append("\nFor each restaurant, suggest 1-2 orders with macro estimates and fit scores.")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n".join(parts)},
    ]
