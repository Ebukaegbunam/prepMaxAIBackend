"""Unit tests for the update_narrative prompt builder."""
import json

from app.llm.prompts.update_narrative import RESPONSE_SCHEMA, VERSION, build_messages


def test_version_is_string():
    assert isinstance(VERSION, str)
    assert VERSION.startswith("v")


def test_returns_two_messages():
    messages = build_messages({"name": "Alex"})
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


def test_system_message_contains_rules():
    messages = build_messages({"name": "Alex"})
    system = messages[0]["content"]
    assert "third-person" in system
    assert "2–4 sentences" in system


def test_user_message_contains_structured_data():
    fields = {"name": "Jordan", "age": 28, "sex": "male"}
    messages = build_messages(fields)
    user_content = messages[1]["content"]
    assert "Structured profile data:" in user_content
    # The JSON should be embedded in the message
    assert '"name"' in user_content
    assert "Jordan" in user_content


def test_free_text_included_when_provided():
    messages = build_messages({"name": "Sam"}, free_text="I train twice a day.")
    user_content = messages[1]["content"]
    assert "I train twice a day." in user_content
    assert "Additional context from the user:" in user_content


def test_free_text_omitted_when_none():
    messages = build_messages({"name": "Sam"}, free_text=None)
    user_content = messages[1]["content"]
    assert "Additional context" not in user_content


def test_free_text_omitted_when_empty_string():
    messages = build_messages({"name": "Sam"}, free_text="")
    user_content = messages[1]["content"]
    assert "Additional context" not in user_content


def test_ends_with_write_narrative():
    messages = build_messages({"name": "Sam"})
    user_content = messages[1]["content"]
    assert user_content.strip().endswith("Write the narrative:")


def test_structured_data_is_valid_json():
    fields = {"name": "Alex", "age": 25, "dietary_restrictions": ["vegan"]}
    messages = build_messages(fields)
    user_content = messages[1]["content"]
    # Extract the JSON portion between "Structured profile data:\n" and next blank line
    lines = user_content.split("\n")
    start = next(i for i, l in enumerate(lines) if l == "Structured profile data:") + 1
    json_lines = []
    for line in lines[start:]:
        if line == "":
            break
        json_lines.append(line)
    parsed = json.loads("\n".join(json_lines))
    assert parsed["name"] == "Alex"
    assert parsed["age"] == 25


def test_response_schema_structure():
    assert RESPONSE_SCHEMA["type"] == "object"
    assert "narrative" in RESPONSE_SCHEMA["properties"]
    assert RESPONSE_SCHEMA["properties"]["narrative"]["type"] == "string"
    assert "narrative" in RESPONSE_SCHEMA["required"]
    assert RESPONSE_SCHEMA.get("additionalProperties") is False
