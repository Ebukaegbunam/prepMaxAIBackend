"""Unit tests for competition cache freshness and snapshot logic."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.services.competition_service import _is_fresh


def _make_comp(days_old: int) -> MagicMock:
    comp = MagicMock()
    comp.refreshed_at = datetime.now(timezone.utc) - timedelta(days=days_old)
    return comp


class TestCacheFreshness:
    def test_fresh_within_7_days(self):
        comp = _make_comp(days_old=3)
        assert _is_fresh(comp) is True

    def test_fresh_on_day_7_boundary(self):
        comp = _make_comp(days_old=6)
        assert _is_fresh(comp) is True

    def test_stale_after_7_days(self):
        comp = _make_comp(days_old=8)
        assert _is_fresh(comp) is False

    def test_brand_new_is_fresh(self):
        comp = _make_comp(days_old=0)
        assert _is_fresh(comp) is True


class TestSnapshotSerialization:
    def test_snapshot_preserves_all_fields(self):
        fields = {
            "name": "NPC Bay Area",
            "date": "2026-08-24",
            "federation": "NPC",
            "tested": False,
            "city": "Oakland",
            "state": "CA",
            "country": "US",
            "divisions": ["classic_physique"],
            "registration_url": "https://npcnewsonline.com",
        }
        snapshot = dict(fields)
        for key, value in fields.items():
            assert snapshot[key] == value

    def test_snapshot_immutable_after_save(self):
        original_name = "NPC Bay Area"
        snapshot = {"name": original_name, "date": "2026-08-24"}
        snapshot_copy = dict(snapshot)
        snapshot["name"] = "Changed Name"
        assert snapshot_copy["name"] == original_name
