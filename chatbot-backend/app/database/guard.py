"""A read-only guard over the dashboard's database.

The assistant answers questions; it never changes anyone's record. That was
already true of the code — `app/hr/queries.py` contains nothing but SELECTs —
but "true today" is not the same as "cannot happen". This makes it structural:
every statement the service sends is inspected first, and anything that writes
to a table other than the assistant's own three is refused before it reaches
SQL Server.

What that protects against is ordinary mistakes rather than attackers: a future
tool that calls `session.execute("UPDATE leaves ...")`, an ORM relationship
that cascades further than expected, a copied snippet. An attacker who can run
code in this process can bypass any in-process check, which is why the README
also gives the SQL Server grants for a login that is read-only at the server —
that is the real boundary, and this is the seatbelt.

Note the connection currently ships configured for `sa`. Until a least
privilege login is created, this guard is the only thing standing between a
stray statement and the HR tables.
"""

import logging
import re
from typing import Optional, Tuple

from sqlalchemy import event
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


class ReadOnlyViolation(RuntimeError):
    """Raised when something tries to modify data the assistant may only read."""


# The assistant's own bookkeeping: chat threads, their messages, and the
# registry of documents an administrator has trained. Everything else in this
# database belongs to the dashboard and is read-only here.
OWN_TABLES = frozenset({"conversations", "messages", "documents"})

# Statements that change data or structure. Anything starting with one of these
# has to name a table this service owns.
WRITE_KEYWORDS = frozenset(
    {
        "insert", "update", "delete", "merge", "truncate",
        "create", "alter", "drop", "rename",
        "grant", "revoke", "deny",
        "exec", "execute", "backup", "restore", "bulk",
    }
)

# Where the table name sits, per statement form.
_TARGET_PATTERNS = (
    re.compile(r"^insert\s+(?:into\s+)?(?P<name>[^\s(]+)", re.IGNORECASE),
    re.compile(r"^update\s+(?P<name>[^\s(]+)", re.IGNORECASE),
    re.compile(r"^delete\s+from\s+(?P<name>[^\s(]+)", re.IGNORECASE),
    re.compile(r"^merge\s+(?:into\s+)?(?P<name>[^\s(]+)", re.IGNORECASE),
    re.compile(r"^truncate\s+table\s+(?P<name>[^\s(]+)", re.IGNORECASE),
    # CREATE/ALTER/DROP TABLE|INDEX|CONSTRAINT ... [ON <table>]
    re.compile(r"^(?:create|alter|drop)\s+(?:unique\s+)?index\s+\S+\s+on\s+(?P<name>[^\s(]+)", re.IGNORECASE),
    re.compile(r"^(?:create|alter|drop)\s+table\s+(?:if\s+(?:not\s+)?exists\s+)?(?P<name>[^\s(]+)", re.IGNORECASE),
)

_COMMENT = re.compile(r"/\*.*?\*/|--[^\n]*", re.DOTALL)


def _normalise(statement: str) -> str:
    """Strip comments and collapse whitespace, so the keyword is the first word."""
    return " ".join(_COMMENT.sub(" ", statement or "").split())


def _bare_name(identifier: str) -> str:
    """`[dbo].[conversations]` -> `conversations`."""
    last = identifier.strip().rstrip(";").split(".")[-1]
    return last.strip("[]\"'`").lower()


def inspect(statement: str) -> Tuple[bool, Optional[str]]:
    """Decide whether a statement may run.

    Returns (allowed, reason). Reads, transaction control and session settings
    pass straight through; a write has to name one of `OWN_TABLES`.
    """
    text = _normalise(statement)
    if not text:
        return True, None

    keyword = text.split(" ", 1)[0].lower().lstrip("(")
    if keyword not in WRITE_KEYWORDS:
        # SELECT, WITH, SET, BEGIN/COMMIT/ROLLBACK, DECLARE, IF, sp_ calls the
        # driver makes on its own behalf.
        return True, None

    if keyword in {"exec", "execute", "grant", "revoke", "deny", "backup", "restore", "bulk"}:
        return False, f"{keyword.upper()} is not permitted from the assistant"

    for pattern in _TARGET_PATTERNS:
        match = pattern.match(text)
        if match:
            table = _bare_name(match.group("name"))
            if table in OWN_TABLES:
                return True, None
            return False, f"{keyword.upper()} on '{table}' — the assistant may only read that table"

    # A write whose target could not be identified is refused: failing closed on
    # something unrecognised is the whole point of the guard.
    return False, f"unrecognised {keyword.upper()} statement"


def install(engine: Engine) -> None:
    """Attach the guard to every statement executed on this engine."""

    @event.listens_for(engine, "before_cursor_execute")
    def _check(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        allowed, reason = inspect(statement)
        if allowed:
            return

        logger.error("read-only guard blocked a statement: %s | %s", reason, _normalise(statement)[:200])
        raise ReadOnlyViolation(
            f"Blocked by the assistant's read-only guard: {reason}. "
            "This service answers questions about HR records and never changes them."
        )

    logger.info(
        "read-only guard active: writes allowed only to %s", ", ".join(sorted(OWN_TABLES))
    )
