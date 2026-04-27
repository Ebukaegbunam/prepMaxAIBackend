"""Unit tests for profile Pydantic schemas."""
import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.profile import ProfileInitializeRequest, ProfilePatchRequest, ProfileResponse


class TestProfileInitializeRequest:
    def test_minimal_valid(self):
        req = ProfileInitializeRequest(name="Alex")
        assert req.name == "Alex"
        assert req.units_weight == "lb"
        assert req.units_measurement == "in"
        assert req.dietary_restrictions == []

    def test_full_valid(self):
        req = ProfileInitializeRequest(
            name="Jordan",
            age=28,
            sex="male",
            height_cm=180.5,
            units_weight="kg",
            units_measurement="cm",
            dietary_restrictions=["vegan"],
            loved_foods=["rice", "chicken"],
            hated_foods=["fish"],
            cooking_skill="intermediate",
            kitchen_equipment=["air fryer"],
            job_type="engineer",
            work_hours="9-5",
            stress_level="moderate",
            sleep_window="22:00-06:00",
            preferred_training_time="morning",
            training_days_per_week=5,
            free_text_about_me="I compete in the men's physique division.",
        )
        assert req.age == 28
        assert req.training_days_per_week == 5

    def test_training_days_min(self):
        req = ProfileInitializeRequest(name="A", training_days_per_week=1)
        assert req.training_days_per_week == 1

    def test_training_days_max(self):
        req = ProfileInitializeRequest(name="A", training_days_per_week=7)
        assert req.training_days_per_week == 7

    def test_training_days_too_low(self):
        with pytest.raises(ValidationError):
            ProfileInitializeRequest(name="A", training_days_per_week=0)

    def test_training_days_too_high(self):
        with pytest.raises(ValidationError):
            ProfileInitializeRequest(name="A", training_days_per_week=8)

    def test_invalid_sex(self):
        with pytest.raises(ValidationError):
            ProfileInitializeRequest(name="A", sex="unknown")

    def test_invalid_units_weight(self):
        with pytest.raises(ValidationError):
            ProfileInitializeRequest(name="A", units_weight="stone")

    def test_invalid_cooking_skill(self):
        with pytest.raises(ValidationError):
            ProfileInitializeRequest(name="A", cooking_skill="expert")

    def test_invalid_stress_level(self):
        with pytest.raises(ValidationError):
            ProfileInitializeRequest(name="A", stress_level="extreme")

    def test_invalid_preferred_training_time(self):
        with pytest.raises(ValidationError):
            ProfileInitializeRequest(name="A", preferred_training_time="night")


class TestProfilePatchRequest:
    def test_empty_is_valid(self):
        req = ProfilePatchRequest()
        assert req.model_dump(exclude_unset=True) == {}

    def test_partial_update(self):
        req = ProfilePatchRequest(name="New Name", age=30)
        dumped = req.model_dump(exclude_unset=True)
        assert dumped == {"name": "New Name", "age": 30}

    def test_free_text_update(self):
        req = ProfilePatchRequest(free_text_update="I just started a bulk.")
        dumped = req.model_dump(exclude_unset=True)
        assert "free_text_update" in dumped

    def test_lists_are_nullable(self):
        req = ProfilePatchRequest(dietary_restrictions=["gluten-free"])
        assert req.dietary_restrictions == ["gluten-free"]

    def test_invalid_sex_rejected(self):
        with pytest.raises(ValidationError):
            ProfilePatchRequest(sex="robot")

    def test_training_days_boundary(self):
        with pytest.raises(ValidationError):
            ProfilePatchRequest(training_days_per_week=8)


class TestProfileResponse:
    def _make_data(self) -> dict:
        now = datetime.now(timezone.utc)
        return {
            "id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "name": "Taylor",
            "created_at": now,
            "updated_at": now,
        }

    def test_minimal_valid(self):
        resp = ProfileResponse(**self._make_data())
        assert resp.name == "Taylor"
        assert resp.narrative is None

    def test_defaults(self):
        resp = ProfileResponse(**self._make_data())
        assert resp.units_weight == "lb"
        assert resp.dietary_restrictions == []
        assert resp.kitchen_equipment == []

    def test_from_attributes(self):
        # Simulates constructing from a SQLAlchemy model instance
        data = self._make_data()
        resp = ProfileResponse.model_validate(data)
        assert resp.id == data["id"]
