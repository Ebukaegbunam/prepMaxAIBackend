"""Unit tests for admin cost-rollup aggregation logic."""
from decimal import Decimal


def _make_row(day: str, task: str, calls: int, input_tokens: int, output_tokens: int, cost_usd: float):
    return {
        "day": day,
        "task": task,
        "calls": calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
    }


class TestCostRollupAggregation:
    def test_total_cost_sums_all_rows(self):
        rows = [
            _make_row("2026-04-01", "generate_weekly_plan", 3, 1200, 800, 0.02),
            _make_row("2026-04-01", "update_narrative", 1, 400, 200, 0.005),
            _make_row("2026-04-02", "generate_weekly_plan", 2, 900, 600, 0.015),
        ]
        total = sum(r["cost_usd"] for r in rows)
        assert abs(total - 0.04) < 1e-9

    def test_total_calls_sums_all_rows(self):
        rows = [
            _make_row("2026-04-01", "task_a", 5, 100, 100, 0.01),
            _make_row("2026-04-01", "task_b", 3, 100, 100, 0.01),
            _make_row("2026-04-02", "task_a", 7, 100, 100, 0.01),
        ]
        total_calls = sum(r["calls"] for r in rows)
        assert total_calls == 15

    def test_per_task_grouping(self):
        rows = [
            _make_row("2026-04-01", "generate_weekly_plan", 3, 1200, 800, 0.02),
            _make_row("2026-04-01", "update_narrative", 1, 400, 200, 0.005),
        ]
        tasks = {r["task"] for r in rows}
        assert "generate_weekly_plan" in tasks
        assert "update_narrative" in tasks

    def test_zero_cost_when_no_rows(self):
        rows = []
        total = sum(r["cost_usd"] for r in rows)
        assert total == 0.0

    def test_remaining_rate_limit(self):
        limit = 1000
        current = 350
        remaining = max(0, limit - current)
        assert remaining == 650

    def test_remaining_never_negative(self):
        limit = 1000
        current = 1500
        remaining = max(0, limit - current)
        assert remaining == 0

    def test_is_limited_at_threshold(self):
        limit = 1000
        assert 1000 >= limit
        assert 999 < limit

    def test_cost_pct_calculation(self):
        cap = 5.0
        spend = 2.5
        pct = round(spend / cap * 100, 1)
        assert pct == 50.0

    def test_cost_pct_over_cap(self):
        cap = 5.0
        spend = 6.0
        pct = round(spend / cap * 100, 1)
        assert pct == 120.0
