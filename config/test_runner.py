"""Test runner that works with Supabase's connection pooler (fixes PD2 issue ISS-02).

Supabase's Session pooler (Supavisor) keeps a pooled server connection to the
temporary `test_postgres` database, and reopens it right away if it is killed.
A plain `DROP DATABASE` then fails with "database test_postgres is being
accessed by other users", both when a run finishes and when the next run
tries to replace the old test database.

PostgreSQL 13+ has `DROP DATABASE ... WITH (FORCE)`, which ends those sessions
and drops the database in one step. This runner makes Django use it, at the
end of a run and for any test database a stopped run left behind, so
`python manage.py test` works on every run without `--keepdb`.
"""
from django.db import connections
from django.test.runner import DiscoverRunner


def force_drop(creation):
    """Replace `creation._destroy_test_db` with a version that uses WITH (FORCE)."""

    def _destroy_test_db(test_database_name, verbosity):
        quoted = creation.connection.ops.quote_name(test_database_name)
        with creation._nodb_cursor() as cursor:
            cursor.execute(f'DROP DATABASE IF EXISTS {quoted} WITH (FORCE)')

    creation._destroy_test_db = _destroy_test_db


class SupabaseTestRunner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        for alias in connections:
            connection = connections[alias]
            if connection.vendor != 'postgresql':
                continue
            creation = connection.creation
            force_drop(creation)
            # A run that crashed or was stopped leaves the old test database behind,
            # sometimes with pooled sessions still holding locks in it. Django would
            # replace it with a plain DROP DATABASE (which those sessions block), so
            # force-drop it first. With --keepdb the existing database is reused instead.
            if not self.keepdb:
                creation._destroy_test_db(creation._get_test_db_name(), self.verbosity)
        return super().setup_databases(**kwargs)
