"""Unit tests for canonicalization helpers and prompt builder."""
import pytest
from app.llm.prompts.canonicalize_exercise import build_messages, RESPONSE_SCHEMA


class TestBuildMessages:
    def test_returns_two_messages(self):
        msgs = build_messages("incline DB press", ["Incline Dumbbell Bench Press"])
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"

    def test_user_message_contains_raw_name(self):
        msgs = build_messages("incline DB press", ["Incline Dumbbell Bench Press"])
        assert "incline DB press" in msgs[1]["content"]

    def test_user_message_contains_canonical_names(self):
        names = ["Flat Barbell Bench Press", "Incline Dumbbell Bench Press"]
        msgs = build_messages("bench", names)
        for name in names:
            assert name in msgs[1]["content"]

    def test_empty_canonical_list(self):
        msgs = build_messages("some exercise", [])
        assert msgs[1]["content"]  # should not crash

    def test_response_schema_valid(self):
        assert "canonical_name" in RESPONSE_SCHEMA["properties"]
        assert "confidence" in RESPONSE_SCHEMA["properties"]
        assert RESPONSE_SCHEMA.get("additionalProperties") is False


class TestPrepDateMath:
    def test_target_date_computed(self):
        from datetime import date, timedelta
        start = date(2026, 5, 4)
        weeks = 16
        expected = start + timedelta(weeks=weeks)
        assert expected == date(2026, 8, 24)

    def test_sixteen_week_prep(self):
        from datetime import date, timedelta
        start = date(2026, 5, 4)
        assert (start + timedelta(weeks=16)).isoformat() == "2026-08-24"
