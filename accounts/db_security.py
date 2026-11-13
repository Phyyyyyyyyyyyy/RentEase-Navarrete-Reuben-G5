"""Keep Django's tables private on Supabase.

Supabase publishes every table in the `public` schema through its Data API
(PostgREST), using the `anon` and `authenticated` roles. RentEase never uses
that API: Django talks to PostgreSQL directly as the `postgres` role, which
bypasses Row Level Security. So after every `migrate` we:

  1. enable RLS on every table in `public` (no policies = the API sees no rows), and
  2. revoke all table/sequence privileges from `anon` and `authenticated`.

This clears Supabase's "RLS Disabled in Public" and "Sensitive Columns Exposed"
warnings and also covers tables added by future migrations.
"""

LOCKDOWN_SQL = """
DO $$
DECLARE
    t record;
BEGIN
    FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t.tablename);
    END LOOP;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon')
       AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated;
        REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
    END IF;
END
$$;
"""


def lock_down_supabase_data_api(sender, using='default', **kwargs):
    from django.db import connections

    connection = connections[using]
    if connection.vendor != 'postgresql':
        return
    with connection.cursor() as cursor:
        cursor.execute(LOCKDOWN_SQL)
