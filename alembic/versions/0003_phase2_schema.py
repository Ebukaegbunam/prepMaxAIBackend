"""Phase 2 schema: canonical_exercise, exercise_alias, prep, workout_template, workout_day, exercise

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-27 20:00:00.000000
"""
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text as sa_text

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.execute("""
        CREATE TABLE canonical_exercise (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL CHECK (category IN ('chest','back','legs','shoulders','arms','core','cardio')),
            primary_muscles JSONB NOT NULL DEFAULT '[]',
            equipment JSONB NOT NULL DEFAULT '[]',
            is_user_created BOOLEAN NOT NULL DEFAULT FALSE,
            created_by_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_canon_ex_name_trgm ON canonical_exercise USING gin (name gin_trgm_ops)")
    op.execute("CREATE INDEX idx_canon_ex_category ON canonical_exercise(category)")

    op.execute("""
        CREATE TABLE exercise_alias (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            canonical_exercise_id UUID NOT NULL REFERENCES canonical_exercise(id) ON DELETE CASCADE,
            alias TEXT NOT NULL,
            source TEXT NOT NULL CHECK (source IN ('seed','llm_resolved','user_confirmed')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_alias_canon ON exercise_alias(canonical_exercise_id)")
    op.execute("CREATE UNIQUE INDEX idx_alias_unique_lower ON exercise_alias(lower(alias))")

    op.execute(sa_text("""
        CREATE TABLE prep (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            division TEXT NOT NULL,
            prep_length_weeks INTEGER NOT NULL DEFAULT 16,
            start_date DATE NOT NULL,
            target_date DATE,
            target_competition_id UUID,
            status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','completed','abandoned')),
            starting_weight_kg NUMERIC(5,2),
            target_weight_kg NUMERIC(5,2),
            starting_bf_pct NUMERIC(4,1),
            target_bf_pct NUMERIC(4,1),
            phase_split JSONB NOT NULL DEFAULT jsonb_build_object('maintenance_weeks',4,'cut_weeks',12),
            current_workout_template_id UUID,
            current_weekly_plan_id UUID,
            completion_notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    op.execute("CREATE INDEX idx_prep_user_id ON prep(user_id)")
    op.execute("ALTER TABLE prep ENABLE ROW LEVEL SECURITY")
    op.execute('CREATE POLICY "prep_select_own" ON prep FOR SELECT USING (user_id = auth.uid())')
    op.execute('CREATE POLICY "prep_insert_own" ON prep FOR INSERT WITH CHECK (user_id = auth.uid())')
    op.execute('CREATE POLICY "prep_update_own" ON prep FOR UPDATE USING (user_id = auth.uid())')
    op.execute('CREATE POLICY "prep_delete_own" ON prep FOR DELETE USING (user_id = auth.uid())')

    op.execute("""
        CREATE TABLE workout_template (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            prep_id UUID NOT NULL REFERENCES prep(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            notes TEXT,
            based_on_parse_id UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_workout_template_prep ON workout_template(prep_id)")
    op.execute("ALTER TABLE workout_template ENABLE ROW LEVEL SECURITY")
    op.execute('CREATE POLICY "wt_select_own" ON workout_template FOR SELECT USING (user_id = auth.uid())')
    op.execute('CREATE POLICY "wt_insert_own" ON workout_template FOR INSERT WITH CHECK (user_id = auth.uid())')
    op.execute('CREATE POLICY "wt_update_own" ON workout_template FOR UPDATE USING (user_id = auth.uid())')
    op.execute('CREATE POLICY "wt_delete_own" ON workout_template FOR DELETE USING (user_id = auth.uid())')

    op.execute("""
        CREATE TABLE workout_day (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            workout_template_id UUID NOT NULL REFERENCES workout_template(id) ON DELETE CASCADE,
            day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
            title TEXT NOT NULL,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_workout_day_template ON workout_day(workout_template_id)")
    op.execute("ALTER TABLE workout_day ENABLE ROW LEVEL SECURITY")
    op.execute('CREATE POLICY "wd_select_own" ON workout_day FOR SELECT USING (user_id = auth.uid())')
    op.execute('CREATE POLICY "wd_insert_own" ON workout_day FOR INSERT WITH CHECK (user_id = auth.uid())')
    op.execute('CREATE POLICY "wd_update_own" ON workout_day FOR UPDATE USING (user_id = auth.uid())')
    op.execute('CREATE POLICY "wd_delete_own" ON workout_day FOR DELETE USING (user_id = auth.uid())')

    op.execute("""
        CREATE TABLE exercise (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            workout_day_id UUID NOT NULL REFERENCES workout_day(id) ON DELETE CASCADE,
            canonical_exercise_id UUID REFERENCES canonical_exercise(id) ON DELETE SET NULL,
            raw_name TEXT NOT NULL,
            "order" INTEGER NOT NULL DEFAULT 0,
            target_sets INTEGER,
            target_reps TEXT,
            target_weight_kg NUMERIC(5,2),
            rest_seconds INTEGER,
            notes TEXT,
            name_match_confidence TEXT CHECK (name_match_confidence IN ('high','medium','low','none')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_exercise_workout_day ON exercise(workout_day_id)")
    op.execute("CREATE INDEX idx_exercise_canonical ON exercise(canonical_exercise_id)")
    op.execute("ALTER TABLE exercise ENABLE ROW LEVEL SECURITY")
    op.execute('CREATE POLICY "ex_select_own" ON exercise FOR SELECT USING (user_id = auth.uid())')
    op.execute('CREATE POLICY "ex_insert_own" ON exercise FOR INSERT WITH CHECK (user_id = auth.uid())')
    op.execute('CREATE POLICY "ex_update_own" ON exercise FOR UPDATE USING (user_id = auth.uid())')
    op.execute('CREATE POLICY "ex_delete_own" ON exercise FOR DELETE USING (user_id = auth.uid())')


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS exercise CASCADE")
    op.execute("DROP TABLE IF EXISTS workout_day CASCADE")
    op.execute("DROP TABLE IF EXISTS workout_template CASCADE")
    op.execute("DROP TABLE IF EXISTS prep CASCADE")
    op.execute("DROP TABLE IF EXISTS exercise_alias CASCADE")
    op.execute("DROP TABLE IF EXISTS canonical_exercise CASCADE")
