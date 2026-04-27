"""Phase 4 schema: weekly_plan, meal_plan, meal_log

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-27 22:00:00.000000
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE weekly_plan (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            prep_id UUID NOT NULL REFERENCES prep(id) ON DELETE CASCADE,
            week_number INTEGER NOT NULL CHECK (week_number >= 1),
            targets JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (prep_id, week_number)
        )
    """)
    op.execute("CREATE INDEX idx_weekly_plan_prep ON weekly_plan(prep_id)")
    op.execute("ALTER TABLE weekly_plan ENABLE ROW LEVEL SECURITY")
    op.execute('CREATE POLICY "wp_select_own" ON weekly_plan FOR SELECT USING (user_id = auth.uid())')
    op.execute('CREATE POLICY "wp_insert_own" ON weekly_plan FOR INSERT WITH CHECK (user_id = auth.uid())')
    op.execute('CREATE POLICY "wp_update_own" ON weekly_plan FOR UPDATE USING (user_id = auth.uid())')
    op.execute('CREATE POLICY "wp_delete_own" ON weekly_plan FOR DELETE USING (user_id = auth.uid())')

    op.execute("""
        CREATE TABLE meal_plan (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            prep_id UUID NOT NULL REFERENCES prep(id) ON DELETE CASCADE,
            weekly_plan_id UUID REFERENCES weekly_plan(id) ON DELETE SET NULL,
            week_number INTEGER NOT NULL CHECK (week_number >= 1),
            day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
            targets JSONB NOT NULL DEFAULT '{}',
            slots JSONB NOT NULL DEFAULT '[]',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (prep_id, week_number, day_of_week)
        )
    """)
    op.execute("CREATE INDEX idx_meal_plan_prep ON meal_plan(prep_id)")
    op.execute("ALTER TABLE meal_plan ENABLE ROW LEVEL SECURITY")
    op.execute('CREATE POLICY "mp_select_own" ON meal_plan FOR SELECT USING (user_id = auth.uid())')
    op.execute('CREATE POLICY "mp_insert_own" ON meal_plan FOR INSERT WITH CHECK (user_id = auth.uid())')
    op.execute('CREATE POLICY "mp_update_own" ON meal_plan FOR UPDATE USING (user_id = auth.uid())')
    op.execute('CREATE POLICY "mp_delete_own" ON meal_plan FOR DELETE USING (user_id = auth.uid())')

    op.execute("""
        CREATE TABLE meal_log (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            prep_id UUID NOT NULL REFERENCES prep(id) ON DELETE CASCADE,
            eaten_at TIMESTAMPTZ NOT NULL,
            slot TEXT,
            name TEXT NOT NULL,
            calories NUMERIC(7,2),
            protein_g NUMERIC(6,2),
            carbs_g NUMERIC(6,2),
            fat_g NUMERIC(6,2),
            source TEXT NOT NULL DEFAULT 'freeform' CHECK (source IN ('planned','swap','freeform')),
            linked_meal_plan_id UUID REFERENCES meal_plan(id) ON DELETE SET NULL,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_meal_log_prep ON meal_log(prep_id)")
    op.execute("CREATE INDEX idx_meal_log_eaten ON meal_log(eaten_at)")
    op.execute("ALTER TABLE meal_log ENABLE ROW LEVEL SECURITY")
    op.execute('CREATE POLICY "ml_select_own" ON meal_log FOR SELECT USING (user_id = auth.uid())')
    op.execute('CREATE POLICY "ml_insert_own" ON meal_log FOR INSERT WITH CHECK (user_id = auth.uid())')
    op.execute('CREATE POLICY "ml_update_own" ON meal_log FOR UPDATE USING (user_id = auth.uid())')
    op.execute('CREATE POLICY "ml_delete_own" ON meal_log FOR DELETE USING (user_id = auth.uid())')


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS meal_log CASCADE")
    op.execute("DROP TABLE IF EXISTS meal_plan CASCADE")
    op.execute("DROP TABLE IF EXISTS weekly_plan CASCADE")
