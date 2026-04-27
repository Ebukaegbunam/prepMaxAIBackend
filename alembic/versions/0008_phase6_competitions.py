"""Phase 6 schema: competition, saved_competition

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-27 23:30:00.000000
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE competition (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            date DATE NOT NULL,
            federation TEXT NOT NULL,
            tested BOOLEAN NOT NULL DEFAULT FALSE,
            city TEXT,
            state TEXT,
            country TEXT DEFAULT 'US',
            lat NUMERIC(9,6),
            lng NUMERIC(9,6),
            divisions JSONB NOT NULL DEFAULT '[]',
            registration_url TEXT,
            source_url TEXT,
            refreshed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (name, date, federation)
        )
    """)
    op.execute("CREATE INDEX idx_competition_date ON competition(date)")
    op.execute("CREATE INDEX idx_competition_federation ON competition(federation)")
    op.execute("CREATE INDEX idx_competition_refreshed ON competition(refreshed_at)")

    op.execute("""
        CREATE TABLE saved_competition (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            competition_id UUID NOT NULL REFERENCES competition(id) ON DELETE CASCADE,
            snapshot JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (user_id, competition_id)
        )
    """)
    op.execute("CREATE INDEX idx_saved_competition_user ON saved_competition(user_id)")
    op.execute("ALTER TABLE saved_competition ENABLE ROW LEVEL SECURITY")
    op.execute('CREATE POLICY "sc_select_own" ON saved_competition FOR SELECT USING (user_id = auth.uid())')
    op.execute('CREATE POLICY "sc_insert_own" ON saved_competition FOR INSERT WITH CHECK (user_id = auth.uid())')
    op.execute('CREATE POLICY "sc_delete_own" ON saved_competition FOR DELETE USING (user_id = auth.uid())')


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS saved_competition CASCADE")
    op.execute("DROP TABLE IF EXISTS competition CASCADE")
