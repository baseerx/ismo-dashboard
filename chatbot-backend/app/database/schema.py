"""Bringing an existing database up to date on startup.

`Base.metadata.create_all` creates tables that are missing but never alters one
that already exists. The chatbot's three tables were first created on the
staging database without `owner_erp_id` / `uploaded_by_erp_id`, so a deployment
pointed at that database would start and then fail on the first query with
"Invalid column name". Adding the columns here keeps that from being a manual
step somebody has to remember on each environment.

Both additions are nullable, so they are safe to apply to a populated table:
existing rows simply have no owner recorded.
"""

import logging
from typing import Iterable, Tuple

from sqlalchemy import text

from app.database.db import engine

logger = logging.getLogger(__name__)

# (table, column, SQL Server type)
EXPECTED_COLUMNS: Tuple[Tuple[str, str, str], ...] = (
    ("conversations", "owner_erp_id", "INT NULL"),
    ("documents", "uploaded_by_erp_id", "INT NULL"),
)


def _missing(connection, columns: Iterable[Tuple[str, str, str]]):
    for table, column, definition in columns:
        exists = connection.execute(
            text(
                """
                SELECT 1
                FROM sys.columns
                WHERE object_id = OBJECT_ID(:table) AND name = :column
                """
            ),
            {"table": table, "column": column},
        ).first()

        table_exists = connection.execute(
            text("SELECT 1 FROM sys.tables WHERE name = :table"), {"table": table}
        ).first()

        if table_exists and not exists:
            yield table, column, definition


def ensure_schema() -> None:
    try:
        with engine.begin() as connection:
            for table, column, definition in _missing(connection, EXPECTED_COLUMNS):
                logger.info("ensure_schema: adding %s.%s", table, column)
                connection.execute(text(f"ALTER TABLE {table} ADD {column} {definition}"))
    except Exception:
        # A schema check failing must not stop the service from starting; the
        # first request will report the real problem far more clearly.
        logger.exception("ensure_schema: could not verify the chatbot tables")
