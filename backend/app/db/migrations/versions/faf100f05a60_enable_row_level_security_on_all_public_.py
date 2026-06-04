"""enable row-level security on all public tables

Revision ID: faf100f05a60
Revises: a596be059b27
Create Date: 2026-06-04 16:32:44.900881

Closes the Supabase `rls_disabled_in_public` advisor. Supabase exposes
every `public`-schema table through its Data API (PostgREST) using the
public anon key (shipped in the frontend bundle). With RLS disabled,
anyone with the project URL + anon key could read/write our data
directly, bypassing the FastAPI backend.

We enable RLS with NO policies, which denies all access to the
anon/authenticated PostgREST roles. Our backend and worker connect as
`postgres` (rolbypassrls = true), so they are unaffected — they never
go through PostgREST anyway. This is purely defense for the Data API
surface we don't use.

Applies to every public table that exists when the migration runs
(app tables + Procrastinate's queue tables). New tables added later
should enable RLS too; the Supabase advisor will flag any that don't.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "faf100f05a60"
down_revision: str | Sequence[str] | None = "a596be059b27"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE r record;
        BEGIN
            FOR r IN
                SELECT tablename FROM pg_tables WHERE schemaname = 'public'
            LOOP
                EXECUTE format(
                    'ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', r.tablename
                );
            END LOOP;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE r record;
        BEGIN
            FOR r IN
                SELECT tablename FROM pg_tables WHERE schemaname = 'public'
            LOOP
                EXECUTE format(
                    'ALTER TABLE public.%I DISABLE ROW LEVEL SECURITY', r.tablename
                );
            END LOOP;
        END $$;
        """
    )
