"""Settings for running the test suite without touching the shared database.

    venv\\Scripts\\python.exe manage.py test jobs --settings=hris.test_settings

The ORM runs against a throwaway SQLite file, built straight from the models
(migrations are skipped: several of them hold SQL Server-only statements).
Anything that reads the SQL Server through SQLAlchemy has to be stubbed in the
test itself.
"""

from .settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}


class _NoMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = _NoMigrations()
