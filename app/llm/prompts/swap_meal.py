"""Prompt for suggesting a meal swap within remaining macro budget."""

VERSION = "v1"

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "alternatives": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "items": {"type": "array", "items": {"type": "object"}},
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
                    "fit_notes": {"type": "string"},
                },
                "required": ["name", "macros"],
                "additionalProperties": False,
            },
        },
        "reasoning": {"type": "string"},
    },
    "required": ["alternatives", "reasoning"],
    "additionalProperties": False,
}


def build_messages(
    current_meal: dict,
    remaining_macros: dict,
    context: str | None,
    pantry: list[str],
) -> list[dict]:
    system = (
        "You are a bodybuilding nutrition coach. Suggest 3 practical meal swaps "
        "that fit within the remaining daily macro budget. Prefer high-protein options."
    )
    parts = [
        f"Current meal: {current_meal.get('name', 'unspecified')} "
        f"(slot: {current_meal.get('slot', 'unspecified')}). "
        f"Macros: {current_meal.get('macros', {})}.",
        f"\nRemaining budget: {remaining_macros['calories']} kcal, "
        f"{remaining_macros['protein_g']}g protein, "
        f"{remaining_macros['carbs_g']}g carbs, {remaining_macros['fat_g']}g fat.",
    ]
    if context:
        parts.append(f"\nContext: {context}")
    if pantry:
        parts.append(f"\nAvailable: {', '.join(pantry)}")
    parts.append("\nSuggest 3 swap alternatives.")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n".join(parts)},
    ]
