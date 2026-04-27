"""Unit tests for progress: trend rollup, SSE formatting, week number, photo compression."""
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from app.lib.sse import delta_event, error_event, final_event, progress_event
from app.services.progress_service import compute_trend


def _make_log(weight_kg: float, days_ago: int = 0) -> MagicMock:
    log = MagicMock()
    log.weight_kg = weight_kg
    log.logged_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return log


class TestComputeTrend:
    def test_empty_logs_returns_insufficient(self):
        trend = compute_trend([])
        assert trend.trajectory == "insufficient_data"
        assert trend.current_avg_7d is None

    def test_single_entry_current_week(self):
        logs = [_make_log(84.5, days_ago=1)]
        trend = compute_trend(logs)
        assert trend.current_avg_7d == 84.5
        assert trend.previous_avg_7d is None
        assert trend.trajectory == "insufficient_data"

    def test_declining_weight_is_on_track(self):
        current_week = [_make_log(83.0, i) for i in range(1, 5)]
        previous_week = [_make_log(84.0, i + 7) for i in range(1, 5)]
        trend = compute_trend(current_week + previous_week)
        assert trend.trajectory == "on_track"
        assert trend.delta_kg is not None
        assert trend.delta_kg < 0

    def test_gaining_weight_detected(self):
        current_week = [_make_log(85.5, i) for i in range(1, 5)]
        previous_week = [_make_log(84.0, i + 7) for i in range(1, 5)]
        trend = compute_trend(current_week + previous_week)
        assert trend.trajectory == "gaining"

    def test_delta_calculation(self):
        current_week = [_make_log(84.0, i) for i in range(1, 5)]
        previous_week = [_make_log(85.0, i + 7) for i in range(1, 5)]
        trend = compute_trend(current_week + previous_week)
        assert trend.delta_kg == pytest.approx(-1.0, abs=0.01)


class TestSSEEvents:
    def test_progress_event_format(self):
        result = progress_event("analyzing_photo")
        assert result.startswith("event: progress\n")
        assert '"stage": "analyzing_photo"' in result
        assert result.endswith("\n\n")

    def test_delta_event_format(self):
        result = delta_event("some streamed text")
        assert result.startswith("event: delta\n")
        assert '"text": "some streamed text"' in result

    def test_final_event_format(self):
        result = final_event({"summary": "great progress", "changes": []})
        assert result.startswith("event: final\n")
        assert '"summary": "great progress"' in result

    def test_error_event_format(self):
        result = error_event("ai_provider_error", "Model unavailable")
        assert result.startswith("event: error\n")
        assert '"code": "ai_provider_error"' in result
        assert '"message": "Model unavailable"' in result

    def test_events_end_with_double_newline(self):
        for event_fn, args in [
            (progress_event, ("stage",)),
            (delta_event, ("text",)),
            (final_event, ({"key": "val"},)),
            (error_event, ("code", "msg")),
        ]:
            assert event_fn(*args).endswith("\n\n")


class TestWeekNumberDerivation:
    def test_week_1_on_start_date(self):
        start = date(2026, 5, 4)
        for_date = date(2026, 5, 4)
        week = max(1, (for_date - start).days // 7 + 1)
        assert week == 1

    def test_week_2_after_7_days(self):
        start = date(2026, 5, 4)
        for_date = date(2026, 5, 11)
        week = max(1, (for_date - start).days // 7 + 1)
        assert week == 2

    def test_week_16_at_end_of_prep(self):
        start = date(2026, 5, 4)
        for_date = date(2026, 8, 17)
        week = max(1, (for_date - start).days // 7 + 1)
        assert week == 16


class TestPhotoCompression:
    def test_compress_reduces_large_image(self):
        from PIL import Image
        import io
        img = Image.new("RGB", (2000, 2000), color=(200, 100, 50))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        original_bytes = buf.getvalue()

        from app.lib.photo_util import compress_for_ai
        compressed = compress_for_ai(original_bytes, max_edge=1024, quality=75)
        img2 = Image.open(io.BytesIO(compressed))
        assert max(img2.size) <= 1024

    def test_small_image_not_upscaled(self):
        from PIL import Image
        import io
        img = Image.new("RGB", (400, 300), color=(100, 150, 200))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")

        from app.lib.photo_util import compress_for_ai
        compressed = compress_for_ai(buf.getvalue(), max_edge=1024)
        img2 = Image.open(io.BytesIO(compressed))
        assert max(img2.size) <= 400

    def test_thumbnail_creates_square(self):
        from PIL import Image
        import io
        img = Image.new("RGB", (1200, 800), color=(10, 20, 30))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")

        from app.lib.photo_util import make_thumbnail
        thumb_bytes = make_thumbnail(buf.getvalue(), size=(256, 256))
        thumb = Image.open(io.BytesIO(thumb_bytes))
        assert thumb.size == (256, 256)
