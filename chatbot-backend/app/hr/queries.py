"""Read-only HR lookups against the dashboard's database.

Why SQL here rather than calls into the Django API: the dashboard's endpoints
take an erp_id as a parameter and apply no authorisation of their own, so
proxying them would add a hop without adding safety, and none of them can
answer "attendance between these two dates" in one call. Reading the tables
directly - with the ERP id fixed by the verified token - is both narrower and
more accurate.

The business rules (financial year, entitlement, the Rest & Recreational
deduction, the day-status precedence) are deliberately the same ones the
Django views apply, so the chatbot and the screens never disagree.
"""

import logging
from datetime import date, datetime, time
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.hr.calendar import (
    each_day,
    financial_year,
    financial_year_label,
    is_weekend,
    overlap_days,
)

logger = logging.getLogger(__name__)

CHECK_IN_DEADLINE = time(8, 30)
CHECK_OUT_DEADLINE = time(16, 0)

# Casual leave is reduced by 10 days once any Rest & Recreational leave is
# taken in the year - the rule the leave balance endpoint applies.
RR_LEAVE_TYPE = "Rest & Recreational Leave"
RR_CASUAL_DEDUCTION = 10


def _row_to_dict(row) -> Dict[str, Any]:
    return dict(row._mapping) if row is not None else {}


# ---------------------------------------------------------------- employees

def get_employee(db: Session, erp_id: int) -> Optional[Dict[str, Any]]:
    row = db.execute(
        text(
            """
            SELECT
                e.erp_id, e.hris_id, e.name, e.section_id, e.gender,
                s.name AS section, d.title AS designation, g.name AS grade
            FROM employees e
            LEFT JOIN sections s ON s.id = e.section_id
            LEFT JOIN designations d ON d.id = e.designation_id
            LEFT JOIN grades g ON g.id = e.grade_id
            WHERE e.erp_id = :erp_id AND e.flag = 1
            """
        ),
        {"erp_id": erp_id},
    ).first()

    return _row_to_dict(row) or None


def find_employees(db: Session, term: str, limit: int = 6) -> List[Dict[str, Any]]:
    """Look an employee up by ERP id or by (part of) their name.

    Only ever reached for an administrator - callers must check that first.
    """
    term = (term or "").strip()
    if not term:
        return []

    if term.isdigit():
        found = get_employee(db, int(term))
        return [found] if found else []

    rows = db.execute(
        text(
            """
            SELECT TOP (:limit)
                e.erp_id, e.hris_id, e.name, e.section_id,
                s.name AS section, d.title AS designation, g.name AS grade
            FROM employees e
            LEFT JOIN sections s ON s.id = e.section_id
            LEFT JOIN designations d ON d.id = e.designation_id
            LEFT JOIN grades g ON g.id = e.grade_id
            WHERE e.flag = 1 AND e.name LIKE :pattern
            ORDER BY e.name
            """
        ),
        {"limit": limit, "pattern": f"%{term}%"},
    ).fetchall()

    return [_row_to_dict(row) for row in rows]


# ------------------------------------------------------------------- leaves

def leave_types(db: Session) -> List[Dict[str, Any]]:
    rows = db.execute(
        text("SELECT leave_type, total_leaves FROM leave_type_counts ORDER BY leave_type")
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def resolve_leave_type(db: Session, spoken: str) -> Optional[str]:
    """Map what a person typed ("casual", "medical leave") to a real type."""
    spoken = (spoken or "").strip().lower()
    if not spoken:
        return None

    known = [row["leave_type"] for row in leave_types(db) if row["leave_type"]]

    for name in known:
        if name.lower() == spoken:
            return name

    # "casual" -> "Casual Leave". Longest match wins, so "maternity leave
    # second" does not resolve to "Maternity Leave First".
    matches = [n for n in known if spoken in n.lower() or n.lower().startswith(spoken)]
    if matches:
        return max(matches, key=len)
    return None


def _consumed_days(
    db: Session, erp_id: int, leave_type: str, fy_start: date, fy_end: date
) -> int:
    """Days of one leave type spoken for in the financial year.

    Pending counts as spent, matching the dashboard: a request awaiting
    approval has already reserved those days.
    """
    rows = db.execute(
        text(
            """
            SELECT start_date, end_date
            FROM leaves
            WHERE erp_id = :erp_id
              AND leave_type = :leave_type
              AND status IN ('approved', 'pending')
              AND start_date <= :fy_end
              AND end_date >= :fy_start
            """
        ),
        {
            "erp_id": erp_id,
            "leave_type": leave_type,
            "fy_start": fy_start,
            "fy_end": fy_end,
        },
    ).fetchall()

    return sum(overlap_days(r.start_date, r.end_date, fy_start, fy_end) for r in rows)


def _has_rr_leave(db: Session, erp_id: int, fy_start: date, fy_end: date) -> bool:
    row = db.execute(
        text(
            """
            SELECT TOP 1 id FROM leaves
            WHERE erp_id = :erp_id
              AND leave_type = :rr_type
              AND status IN ('approved', 'pending')
              AND start_date <= :fy_end
              AND end_date >= :fy_start
            """
        ),
        {
            "erp_id": erp_id,
            "rr_type": RR_LEAVE_TYPE,
            "fy_start": fy_start,
            "fy_end": fy_end,
        },
    ).first()
    return row is not None


def leave_balance(
    db: Session,
    erp_id: int,
    leave_type: Optional[str] = None,
    on: Optional[date] = None,
) -> Dict[str, Any]:
    """Entitlement, days used and days left, for one type or for all of them."""
    fy_start, fy_end = financial_year(on)
    entitlements = leave_types(db)

    if leave_type:
        entitlements = [e for e in entitlements if e["leave_type"] == leave_type]

    rows: List[Dict[str, Any]] = []
    for entitlement in entitlements:
        name = entitlement["leave_type"]
        allowed = entitlement["total_leaves"]
        used = _consumed_days(db, erp_id, name, fy_start, fy_end)

        if name.lower() == "casual leave" and _has_rr_leave(db, erp_id, fy_start, fy_end):
            used += RR_CASUAL_DEDUCTION

        # Types with no entitlement configured and nothing used are noise: a
        # list of twenty zeroes hides the two lines that matter.
        if not leave_type and not allowed and not used:
            continue

        rows.append(
            {
                "leave_type": name,
                "total_allowed": allowed,
                "used_days": used,
                "remaining": (allowed - used) if allowed is not None else None,
            }
        )

    rows.sort(key=lambda r: r["leave_type"])

    return {
        "erp_id": erp_id,
        "financial_year": financial_year_label(fy_start, fy_end),
        "period": {"start": fy_start.isoformat(), "end": fy_end.isoformat()},
        "balances": rows,
    }


def leave_history(
    db: Session,
    erp_id: int,
    start: date,
    end: date,
    status: Optional[str] = None,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    """Leave requests overlapping [start, end], most recent first."""
    clause = "AND l.status = :status" if status else ""

    rows = db.execute(
        text(
            f"""
            SELECT TOP (:limit)
                l.id, l.leave_type, l.start_date, l.end_date, l.status,
                l.reason, l.created_at, l.head_erpid,
                h.name AS approver_name
            FROM leaves l
            LEFT JOIN employees h ON h.erp_id = l.head_erpid
            WHERE l.erp_id = :erp_id
              AND l.start_date <= :end
              AND l.end_date >= :start
              {clause}
            ORDER BY l.start_date DESC
            """
        ),
        {"limit": limit, "erp_id": erp_id, "start": start, "end": end, "status": status},
    ).fetchall()

    history = []
    for row in rows:
        record = _row_to_dict(row)
        record["days"] = overlap_days(
            record["start_date"],
            record["end_date"],
            record["start_date"],
            record["end_date"],
        )
        history.append(record)

    return history


def official_work(
    db: Session, erp_id: int, start: date, end: date, limit: int = 500
) -> List[Dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT TOP (:limit)
                o.id, o.leave_type, o.start_date, o.end_date, o.status, o.reason
            FROM official_work_leaves o
            WHERE o.erp_id = :erp_id
              AND o.start_date <= :end
              AND o.end_date >= :start
            ORDER BY o.start_date DESC
            """
        ),
        {"limit": limit, "erp_id": erp_id, "start": start, "end": end},
    ).fetchall()

    return [_row_to_dict(row) for row in rows]


# --------------------------------------------------------------- attendance

def _punches_by_day(db: Session, hris_id: int, start: date, end: date) -> Dict[date, Dict]:
    rows = db.execute(
        text(
            """
            SELECT
                CAST(timestamp AS DATE) AS day,
                MIN(CASE WHEN status = 'Checked In' THEN timestamp END) AS checkin_time,
                MAX(CASE WHEN status IN ('Checked Out', 'Early Checked Out')
                         THEN timestamp END) AS checkout_time,
                COUNT(*) AS punches
            FROM attendance
            WHERE user_id = :hris_id
              AND CAST(timestamp AS DATE) BETWEEN :start AND :end
            GROUP BY CAST(timestamp AS DATE)
            """
        ),
        {"hris_id": hris_id, "start": start, "end": end},
    ).fetchall()

    return {row.day: _row_to_dict(row) for row in rows}


def _approved_spans(db: Session, table: str, erp_id: int, start: date, end: date) -> List[Dict]:
    # `table` is never user input - the two call sites below pass a literal.
    rows = db.execute(
        text(
            f"""
            SELECT leave_type, start_date, end_date
            FROM {table}
            WHERE erp_id = :erp_id
              AND status = 'approved'
              AND start_date <= :end
              AND end_date >= :start
            """
        ),
        {"erp_id": erp_id, "start": start, "end": end},
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def _holidays(db: Session, start: date, end: date) -> Dict[date, str]:
    rows = db.execute(
        text("SELECT name, date FROM public_holidays WHERE date BETWEEN :start AND :end"),
        {"start": start, "end": end},
    ).fetchall()
    return {row.date: row.name for row in rows}


def _assess(checkin: Optional[datetime], checkout: Optional[datetime]) -> Dict[str, str]:
    late = "-"
    early = "-"
    if checkin is not None:
        late = "Late" if checkin.time() > CHECK_IN_DEADLINE else "On Time"
    if checkout is not None:
        early = "Early" if checkout.time() < CHECK_OUT_DEADLINE else "On Time"
    return {"late_status": late, "early_status": early}


def attendance_range(db: Session, erp_id: int, start: date, end: date) -> Dict[str, Any]:
    """One row per calendar day.

    Status precedence is the dashboard's: present > leave > official work >
    holiday > weekend > absent.
    """
    employee = get_employee(db, erp_id)
    if not employee:
        return {"erp_id": erp_id, "employee": None, "days": [], "summary": {}}

    punches = _punches_by_day(db, employee["hris_id"], start, end)
    leaves = _approved_spans(db, "leaves", erp_id, start, end)
    official = _approved_spans(db, "official_work_leaves", erp_id, start, end)
    holidays = _holidays(db, start, end)

    def covering(spans: List[Dict], day: date) -> Optional[str]:
        for span in spans:
            if span["start_date"] <= day <= span["end_date"]:
                return span["leave_type"] or "Leave"
        return None

    days: List[Dict[str, Any]] = []
    summary = {
        "present": 0,
        "leave": 0,
        "official": 0,
        "holiday": 0,
        "weekend": 0,
        "absent": 0,
        "late": 0,
        "early_out": 0,
    }

    for day in each_day(start, end):
        punch = punches.get(day, {})
        checkin = punch.get("checkin_time")
        checkout = punch.get("checkout_time")
        assessed = _assess(checkin, checkout)

        on_leave = covering(leaves, day)
        on_official = covering(official, day)

        if checkin is not None or checkout is not None:
            flag, flag_type = "Present", "present"
        elif on_leave:
            flag, flag_type = on_leave, "leave"
        elif on_official:
            flag, flag_type = on_official, "official"
        elif day in holidays:
            flag, flag_type = holidays[day], "holiday"
        elif is_weekend(day):
            flag, flag_type = "Weekend", "weekend"
        else:
            flag, flag_type = "Absent", "absent"

        summary[flag_type] = summary.get(flag_type, 0) + 1
        if assessed["late_status"] == "Late":
            summary["late"] += 1
        if assessed["early_status"] == "Early":
            summary["early_out"] += 1

        days.append(
            {
                "date": day.isoformat(),
                "checkin_time": checkin.strftime("%H:%M") if checkin else None,
                "checkout_time": checkout.strftime("%H:%M") if checkout else None,
                "late_status": assessed["late_status"],
                "early_status": assessed["early_status"],
                "status": flag,
                "status_type": flag_type,
            }
        )

    return {
        "erp_id": erp_id,
        "employee": employee,
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "days": days,
        "summary": summary,
    }


def attendance_day(db: Session, erp_id: int, day: Optional[date] = None) -> Dict[str, Any]:
    """One day's snapshot, the shape the dashboard's "my today" card shows."""
    day = day or date.today()
    ranged = attendance_range(db, erp_id, day, day)

    if not ranged.get("days"):
        return {"erp_id": erp_id, "date": day.isoformat(), "found": False}

    snapshot = dict(ranged["days"][0])
    snapshot.update(
        {
            "erp_id": erp_id,
            "found": True,
            "name": ranged["employee"]["name"],
            "section": ranged["employee"].get("section"),
            "designation": ranged["employee"].get("designation"),
        }
    )
    return snapshot
