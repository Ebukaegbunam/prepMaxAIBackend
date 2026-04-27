"""Phase 3 schema: workout_session, set_log, cardio_log

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-27 21:00:00.000000
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE workout_session (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            prep_id UUID NOT NULL REFERENCES prep(id) ON DELETE CASCADE,
            workout_day_id UUID REFERENCES workout_day(id) ON DELETE SET NULL,
            title TEXT,
            started_at TIMESTAMPTZ NOT NULL,
            completed_at TIMESTAMPTZ,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_workout_session_prep ON workout_session(prep_id)")
    op.execute("CREATE INDEX idx_workout_session_started ON workout_session(started_at)")
    op.execute("ALTER TABLE workout_session ENABLE ROW LEVEL SECURITY")
    op.execute('CREATE POLICY "ws_select_own" ON workout_session FOR SELECT USING (user_id = auth.uid())')
    op.execute('CREATE POLICY "ws_insert_own" ON workout_session FOR INSERT WITH CHECK (user_id = auth.uid())')
    op.execute('CREATE POLICY "ws_update_own" ON workout_session FOR UPDATE USING (user_id = auth.uid())')
    op.execute('CREATE POLICY "ws_delete_own" ON workout_session FOR DELETE USING (user_id = auth.uid())')

    op.execute("""
        CREATE TABLE set_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            workout_session_id UUID NOT NULL REFERENCES workout_session(id) ON DELETE CASCADE,
            exercise_id UUID REFERENCES exercise(id) ON DELETE SET NULL,
            canonical_exercise_id UUID REFERENCES canonical_exercise(id) ON DELETE SET NULL,
            exercise_name_raw TEXT NOT NULL,
            set_number INTEGER NOT NULL DEFAULT 1,
            weight_kg NUMERIC(6,2),
            reps INTEGER,
            rpe NUMERIC(3,1),
            performed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_set_log_session ON set_log(workout_session_id)")
    op.execute("CREATE INDEX idx_set_log_canonical ON set_log(canonical_exercise_id)")
    op.execute("CREATE INDEX idx_set_log_performed ON set_log(performed_at)")
    op.execute("ALTER TABLE set_log ENABLE ROW LEVEL SECURITY")
    op.execute('CREATE POLICY "sl_select_own" ON set_log FOR SELECT USING (user_id = auth.uid())')
    op.execute('CREATE POLICY "sl_insert_own" ON set_log FOR INSERT WITH CHECK (user_id = auth.uid())')
    op.execute('CREATE POLICY "sl_update_own" ON set_log FOR UPDATE USING (user_id = auth.uid())')
    op.execute('CREATE POLICY "sl_delete_own" ON set_log FOR DELETE USING (user_id = auth.uid())')

    op.execute("""
        CREATE TABLE cardio_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            prep_id UUID NOT NULL REFERENCES prep(id) ON DELETE CASCADE,
            performed_at TIMESTAMPTZ NOT NULL,
            modality TEXT NOT NULL,
            duration_min INTEGER,
            avg_hr INTEGER,
            calories_burned_estimate INTEGER,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_cardio_log_prep ON cardio_log(prep_id)")
    op.execute("CREATE INDEX idx_cardio_log_performed ON cardio_log(performed_at)")
    op.execute("ALTER TABLE cardio_log ENABLE ROW LEVEL SECURITY")
    op.execute('CREATE POLICY "cl_select_own" ON cardio_log FOR SELECT USING (user_id = auth.uid())')
    op.execute('CREATE POLICY "cl_insert_own" ON cardio_log FOR INSERT WITH CHECK (user_id = auth.uid())')
    op.execute('CREATE POLICY "cl_update_own" ON cardio_log FOR UPDATE USING (user_id = auth.uid())')
    op.execute('CREATE POLICY "cl_delete_own" ON cardio_log FOR DELETE USING (user_id = auth.uid())')


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS cardio_log CASCADE")
    op.execute("DROP TABLE IF EXISTS set_log CASCADE")
    op.execute("DROP TABLE IF EXISTS workout_session CASCADE")
