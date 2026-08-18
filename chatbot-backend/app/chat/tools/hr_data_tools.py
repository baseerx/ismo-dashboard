"""The HR lookups the model is allowed to make.

Note what these functions do *not* take: an employee id. The ERP id comes from
the `Identity` the caller resolved out of the signed token, so there is no
argument the model could fill in to reach somebody else's record. The worst a
confused model can do is fetch the asker's own data for the wrong dates - and
the answer always states the dates it used.
"""

import logging
from datetime import date, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.auth.identity import Identity
from app.hr import queries as hr

logger = logging.getLogger(__name__)

# A model asking for "all of it" gets a year, not the entire employment history.
DEFAULT_LOOKBACK_DAYS = 365


def _window(start: Optional[str], end: Optional[str]) -> tuple[date, date]:
    today = date.today()

    def parse(value: Optional[str], fallback: date) -> date:
        if not value:
            return fallback
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            logger.info("_window: unusable date %r, falling back to %s", value, fallback)
            return fallback

    first = parse(start, today - timedelta(days=DEFAULT_LOOKBACK_DAYS))
    last = parse(end, today)

    if last < first:
        first, last = last, first

    return first, last


def get_leave_balance(
    db: Session, identity: Identity, leave_type: Optional[str] = None
) -> Dict[str, Any]:
    resolved = hr.resolve_leave_type(db, leave_type) if leave_type else None
    return hr.leave_balance(db, identity.erp_id, leave_type=resolved)


def get_leave_history(
    db: Session,
    identity: Identity,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    start, end = _window(start_date, end_date)
    records = hr.leave_history(db, identity.erp_id, start, end, status=status)
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "count": len(records),
        "records": records,
    }


def get_attendance(
    db: Session,
    identity: Identity,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    start, end = _window(start_date, end_date)
    ranged = hr.attendance_range(db, identity.erp_id, start, end)
    return {
        "period": ranged.get("period"),
        "summary": ranged.get("summary"),
        "days": ranged.get("days"),
    }


def get_official_work(
    db: Session,
    identity: Identity,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    start, end = _window(start_date, end_date)
    records = hr.official_work(db, identity.erp_id, start, end)
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "count": len(records),
        "records": records,
    }


def get_my_profile(db: Session, identity: Identity) -> Dict[str, Any]:
    employee = hr.get_employee(db, identity.erp_id) or {}
    return {
        "erp_id": identity.erp_id,
        "name": employee.get("name") or identity.name,
        "section": employee.get("section") or identity.section_name,
        "designation": employee.get("designation"),
        "grade": employee.get("grade"),
        "is_admin": identity.is_admin,
    }
