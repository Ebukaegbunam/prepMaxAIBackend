"""Phase 1 tables: profile, ai_request_log, rate_limit_counter

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-27 19:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE ai_request_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            task TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            prompt_version TEXT,
            input_tokens INTEGER,
            output_tokens INTEGER,
            cost_usd NUMERIC(10, 6),
            latency_ms INTEGER,
            status TEXT NOT NULL DEFAULT 'success',
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX idx_ai_log_user_created ON ai_request_log(user_id, created_at DESC)"
    )

    op.execute("""
        CREATE TABLE rate_limit_counter (
            user_id UUID NOT NULL,
            hour_bucket TIMESTAMPTZ NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, hour_bucket)
        )
    """)
    op.execute(
        "CREATE INDEX idx_rate_limit_user_hour ON rate_limit_counter(user_id, hour_bucket DESC)"
    )

    op.execute("""
        CREATE TABLE profile (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            age INTEGER,
            sex TEXT CHECK (sex IN ('male', 'female', 'other')),
            height_cm NUMERIC,
            units_weight TEXT NOT NULL DEFAULT 'lb' CHECK (units_weight IN ('lb', 'kg')),
            units_measurement TEXT NOT NULL DEFAULT 'in' CHECK (units_measurement IN ('in', 'cm')),
            dietary_restrictions JSONB NOT NULL DEFAULT '[]',
            loved_foods JSONB NOT NULL DEFAULT '[]',
            hated_foods JSONB NOT NULL DEFAULT '[]',
            cooking_skill TEXT CHECK (cooking_skill IN ('beginner', 'intermediate', 'advanced')),
            kitchen_equipment JSONB NOT NULL DEFAULT '[]',
            job_type TEXT,
            work_hours TEXT,
            stress_level TEXT CHECK (stress_level IN ('low', 'moderate', 'high')),
            sleep_window TEXT,
            preferred_training_time TEXT CHECK (
                preferred_training_time IN ('morning', 'midday', 'afternoon', 'evening')
            ),
            training_days_per_week INTEGER CHECK (training_days_per_week BETWEEN 1 AND 7),
            narrative TEXT,
            narrative_updated_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("ALTER TABLE profile ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY "profile_select_own" ON profile
            FOR SELECT USING (user_id = auth.uid())
    """)
    op.execute("""
        CREATE POLICY "profile_insert_own" ON profile
            FOR INSERT WITH CHECK (user_id = auth.uid())
    """)
    op.execute("""
        CREATE POLICY "profile_update_own" ON profile
            FOR UPDATE USING (user_id = auth.uid())
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS profile CASCADE")
    op.execute("DROP TABLE IF EXISTS rate_limit_counter CASCADE")
    op.execute("DROP TABLE IF EXISTS ai_request_log CASCADE")
