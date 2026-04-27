"""Phase 5 schema: weight_log, measurement_log, photo, check_in, check_in_photo, ai_report

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-27 23:00:00.000000
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE weight_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            prep_id UUID NOT NULL REFERENCES prep(id) ON DELETE CASCADE,
            logged_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            weight_kg NUMERIC(5,2) NOT NULL,
            source TEXT NOT NULL DEFAULT 'manual',
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_weight_log_prep ON weight_log(prep_id)")
    op.execute("CREATE INDEX idx_weight_log_logged ON weight_log(logged_at)")
    op.execute("ALTER TABLE weight_log ENABLE ROW LEVEL SECURITY")
    op.execute('CREATE POLICY "wl_select_own" ON weight_log FOR SELECT USING (user_id = auth.uid())')
    op.execute('CREATE POLICY "wl_insert_own" ON weight_log FOR INSERT WITH CHECK (user_id = auth.uid())')
    op.execute('CREATE POLICY "wl_update_own" ON weight_log FOR UPDATE USING (user_id = auth.uid())')
    op.execute('CREATE POLICY "wl_delete_own" ON weight_log FOR DELETE USING (user_id = auth.uid())')

    op.execute("""
        CREATE TABLE measurement_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            prep_id UUID NOT NULL REFERENCES prep(id) ON DELETE CASCADE,
            logged_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            chest_cm NUMERIC(5,1),
            waist_cm NUMERIC(5,1),
            hips_cm NUMERIC(5,1),
            left_arm_cm NUMERIC(5,1),
            right_arm_cm NUMERIC(5,1),
            left_thigh_cm NUMERIC(5,1),
            right_thigh_cm NUMERIC(5,1),
            left_calf_cm NUMERIC(5,1),
            right_calf_cm NUMERIC(5,1),
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_measurement_log_prep ON measurement_log(prep_id)")
    op.execute("ALTER TABLE measurement_log ENABLE ROW LEVEL SECURITY")
    op.execute('CREATE POLICY "mesl_select_own" ON measurement_log FOR SELECT USING (user_id = auth.uid())')
    op.execute('CREATE POLICY "mesl_insert_own" ON measurement_log FOR INSERT WITH CHECK (user_id = auth.uid())')
    op.execute('CREATE POLICY "mesl_update_own" ON measurement_log FOR UPDATE USING (user_id = auth.uid())')
    op.execute('CREATE POLICY "mesl_delete_own" ON measurement_log FOR DELETE USING (user_id = auth.uid())')

    op.execute("""
        CREATE TABLE photo (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            prep_id UUID NOT NULL REFERENCES prep(id) ON DELETE CASCADE,
            storage_key TEXT NOT NULL,
            thumbnail_key TEXT,
            taken_at TIMESTAMPTZ NOT NULL,
            week_number INTEGER,
            angle TEXT,
            body_part TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_photo_prep ON photo(prep_id)")
    op.execute("ALTER TABLE photo ENABLE ROW LEVEL SECURITY")
    op.execute('CREATE POLICY "ph_select_own" ON photo FOR SELECT USING (user_id = auth.uid())')
    op.execute('CREATE POLICY "ph_insert_own" ON photo FOR INSERT WITH CHECK (user_id = auth.uid())')
    op.execute('CREATE POLICY "ph_delete_own" ON photo FOR DELETE USING (user_id = auth.uid())')

    op.execute("""
        CREATE TABLE check_in (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            prep_id UUID NOT NULL REFERENCES prep(id) ON DELETE CASCADE,
            week_number INTEGER NOT NULL,
            completed_at TIMESTAMPTZ NOT NULL,
            weight_kg NUMERIC(5,2),
            mood INTEGER CHECK (mood BETWEEN 1 AND 5),
            energy INTEGER CHECK (energy BETWEEN 1 AND 5),
            sleep INTEGER CHECK (sleep BETWEEN 1 AND 5),
            training_quality INTEGER CHECK (training_quality BETWEEN 1 AND 5),
            notes TEXT,
            measurement_log_id UUID REFERENCES measurement_log(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_check_in_prep ON check_in(prep_id)")
    op.execute("ALTER TABLE check_in ENABLE ROW LEVEL SECURITY")
    op.execute('CREATE POLICY "ci_select_own" ON check_in FOR SELECT USING (user_id = auth.uid())')
    op.execute('CREATE POLICY "ci_insert_own" ON check_in FOR INSERT WITH CHECK (user_id = auth.uid())')
    op.execute('CREATE POLICY "ci_delete_own" ON check_in FOR DELETE USING (user_id = auth.uid())')

    op.execute("""
        CREATE TABLE check_in_photo (
            check_in_id UUID NOT NULL REFERENCES check_in(id) ON DELETE CASCADE,
            photo_id UUID NOT NULL REFERENCES photo(id) ON DELETE CASCADE,
            PRIMARY KEY (check_in_id, photo_id)
        )
    """)

    op.execute("""
        CREATE TABLE ai_report (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            prep_id UUID NOT NULL REFERENCES prep(id) ON DELETE CASCADE,
            week_number INTEGER NOT NULL,
            content JSONB NOT NULL DEFAULT '{}',
            ai_request_id UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (prep_id, week_number)
        )
    """)
    op.execute("CREATE INDEX idx_ai_report_prep ON ai_report(prep_id)")
    op.execute("ALTER TABLE ai_report ENABLE ROW LEVEL SECURITY")
    op.execute('CREATE POLICY "ar_select_own" ON ai_report FOR SELECT USING (user_id = auth.uid())')
    op.execute('CREATE POLICY "ar_insert_own" ON ai_report FOR INSERT WITH CHECK (user_id = auth.uid())')
    op.execute('CREATE POLICY "ar_update_own" ON ai_report FOR UPDATE USING (user_id = auth.uid())')


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ai_report CASCADE")
    op.execute("DROP TABLE IF EXISTS check_in_photo CASCADE")
    op.execute("DROP TABLE IF EXISTS check_in CASCADE")
    op.execute("DROP TABLE IF EXISTS photo CASCADE")
    op.execute("DROP TABLE IF EXISTS measurement_log CASCADE")
    op.execute("DROP TABLE IF EXISTS weight_log CASCADE")
