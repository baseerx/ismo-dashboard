"""Wording the data answers.

These sentences are assembled in code rather than generated. A leave balance or
an attendance record is a factual claim about somebody's employment, and a
local 7B model paraphrasing a number is a real risk of restating it wrongly —
"19 remaining" arriving as "about 20". The model writes the policy answers,
where prose is the point; here it writes nothing.

Every answer states the period it used, so a reader can see whether the
question was understood before trusting the figure.
"""

from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from app.chat.dates import DateRange
from app.chat.schemas import Column, DataBlock, ReportOffer

STATUS_WORDS = {
    "approved": "approved",
    "pending": "awaiting approval",
    "rejected": "rejected",
}


def _who(employee: Dict[str, Any], is_self: bool) -> str:
    if is_self:
        return "You"
    return f"{employee.get('name', 'This employee')} (ERP {employee.get('erp_id')})"


def _possessive(employee: Dict[str, Any], is_self: bool) -> str:
    if is_self:
        return "Your"
    return f"{employee.get('name', 'This employee')}'s"


def _day(value: Any) -> str:
    if isinstance(value, (date,)):
        return value.strftime("%d %b %Y")
    return str(value or "-")


# ------------------------------------------------------------ leave balance

def leave_balance(
    employee: Dict[str, Any],
    balance: Dict[str, Any],
    is_self: bool,
    leave_type: Optional[str] = None,
) -> Tuple[str, Optional[DataBlock]]:
    rows = balance.get("balances", [])
    year = balance.get("financial_year")

    if not rows:
        which = f"{leave_type} " if leave_type else ""
        return (
            f"I could not find a {which}entitlement configured for financial year {year}. "
            "The leave types and their yearly allowances are set up by HR in the leave "
            "type settings.",
            None,
        )

    if leave_type and len(rows) == 1:
        row = rows[0]
        remaining = row["remaining"]
        used = row["used_days"]
        allowed = row["total_allowed"]

        if remaining is None:
            answer = (
                f"{_possessive(employee, is_self)} **{row['leave_type']}** has no yearly "
                f"allowance configured. {used} day(s) are recorded against it in "
                f"financial year {year}."
            )
        else:
            answer = (
                f"{_who(employee, is_self)} {'have' if is_self else 'has'} "
                f"**{remaining} of {allowed} day(s)** of **{row['leave_type']}** left for "
                f"financial year {year} — {used} day(s) already used or awaiting approval."
            )
            if remaining <= 0:
                answer += " That allowance is fully used for this year."
    else:
        answer = (
            f"Here is {_possessive(employee, is_self).lower()} leave position for financial "
            f"year {year}. Days that are still awaiting approval are counted as used, the "
            "same way the leave screens count them."
        )

    block = DataBlock(
        title=f"Leave balance — financial year {year}",
        columns=[
            Column(key="leave_type", label="Leave Type"),
            Column(key="total_allowed", label="Allowed"),
            Column(key="used_days", label="Used"),
            Column(key="remaining", label="Remaining"),
        ],
        rows=[
            {
                "leave_type": row["leave_type"],
                "total_allowed": row["total_allowed"] if row["total_allowed"] is not None else "-",
                "used_days": row["used_days"],
                "remaining": row["remaining"] if row["remaining"] is not None else "-",
            }
            for row in rows
        ],
        note=(
            "Casual Leave is reduced by 10 days once Rest & Recreational Leave is taken "
            "in the same year."
            if any(r["leave_type"].lower() == "casual leave" for r in rows)
            else None
        ),
    )

    return answer, block


# ------------------------------------------------------------ leave history

def leave_history(
    employee: Dict[str, Any],
    records: List[Dict[str, Any]],
    period: DateRange,
    is_self: bool,
) -> Tuple[str, Optional[DataBlock]]:
    if not records:
        answer = (
            f"{_who(employee, is_self)} {'have' if is_self else 'has'} no leave records for "
            f"**{period.label}** ({period.describe()})."
        )
        if not period.explicit:
            answer += " I looked at the current financial year — name a period if you meant another."
        return answer, None

    total_days = sum(record.get("days") or 0 for record in records)
    by_status: Dict[str, int] = {}
    for record in records:
        key = (record.get("status") or "").lower() or "unknown"
        by_status[key] = by_status.get(key, 0) + 1

    breakdown = ", ".join(
        f"{count} {STATUS_WORDS.get(status, status)}" for status, count in sorted(by_status.items())
    )

    answer = (
        f"{_who(employee, is_self)} {'have' if is_self else 'has'} **{len(records)} leave "
        f"record(s)** covering **{total_days} day(s)** in **{period.label}** "
        f"({period.describe()}) — {breakdown}."
    )
    if not period.explicit:
        answer += " That is the current financial year; ask for a date range to narrow it."

    block = DataBlock(
        title=f"Leave records — {period.label}",
        columns=[
            Column(key="leave_type", label="Leave Type"),
            Column(key="start_date", label="From"),
            Column(key="end_date", label="To"),
            Column(key="days", label="Days"),
            Column(key="status", label="Status"),
            Column(key="approver_name", label="Section Head"),
        ],
        rows=[
            {
                "leave_type": record.get("leave_type") or "-",
                "start_date": _day(record.get("start_date")),
                "end_date": _day(record.get("end_date")),
                "days": record.get("days"),
                "status": (record.get("status") or "-").title(),
                "approver_name": record.get("approver_name") or "-",
            }
            for record in records
        ],
        summary={"records": len(records), "total_days": total_days},
    )

    return answer, block


# --------------------------------------------------------------- attendance

def attendance_day(
    employee: Dict[str, Any], snapshot: Dict[str, Any], day: date, is_self: bool
) -> Tuple[str, Optional[DataBlock]]:
    if not snapshot.get("found"):
        return (
            f"I could not find an attendance record for {_day(day)}.",
            None,
        )

    who = _who(employee, is_self)
    verb_were = "were" if is_self else "was"
    checkin = snapshot.get("checkin_time")
    checkout = snapshot.get("checkout_time")
    status = snapshot.get("status")
    status_type = snapshot.get("status_type")

    if status_type == "present":
        parts = [f"{who} {verb_were} marked **present** on {_day(day)}."]
        if checkin:
            arrival = snapshot.get("late_status")
            parts.append(
                f"First check-in **{checkin}**"
                + (f" ({arrival.lower()} against the 08:30 deadline)." if arrival != "-" else ".")
            )
        else:
            parts.append("No check-in punch was recorded.")
        if checkout:
            departure = snapshot.get("early_status")
            parts.append(
                f"Last check-out **{checkout}**"
                + (
                    " — that is before the 16:00 deadline."
                    if departure == "Early"
                    else " (on time against the 16:00 deadline)."
                    if departure != "-"
                    else "."
                )
            )
        else:
            parts.append("No check-out punch has been recorded yet.")
        answer = " ".join(parts)
    elif status_type == "leave":
        answer = f"{who} {verb_were} on **{status}** on {_day(day)}, so no attendance was expected."
    elif status_type == "official":
        answer = f"{who} {verb_were} on **official work** ({status}) on {_day(day)}."
    elif status_type == "holiday":
        answer = f"{_day(day)} was a public holiday — **{status}**."
    elif status_type == "weekend":
        answer = f"{_day(day)} was a **weekend**, so no attendance was expected."
    else:
        answer = (
            f"{who} {verb_were} marked **absent** on {_day(day)} — no punch, approved leave, "
            "official work or holiday was found for that day."
        )

    block = DataBlock(
        title=f"Attendance — {_day(day)}",
        columns=[
            Column(key="date", label="Date"),
            Column(key="checkin_time", label="Check In"),
            Column(key="checkout_time", label="Check Out"),
            Column(key="late_status", label="Arrival"),
            Column(key="early_status", label="Departure"),
            Column(key="status", label="Day Status"),
        ],
        rows=[
            {
                "date": _day(day),
                "checkin_time": checkin or "-",
                "checkout_time": checkout or "-",
                "late_status": snapshot.get("late_status") or "-",
                "early_status": snapshot.get("early_status") or "-",
                "status": status or "-",
            }
        ],
    )

    return answer, block


def attendance_range(
    employee: Dict[str, Any], ranged: Dict[str, Any], period: DateRange, is_self: bool
) -> Tuple[str, Optional[DataBlock]]:
    days = ranged.get("days", [])
    summary = ranged.get("summary", {})

    if not days:
        return f"I found no attendance data for **{period.label}** ({period.describe()}).", None

    working_days = summary.get("present", 0) + summary.get("absent", 0) + summary.get("leave", 0) + summary.get("official", 0)

    answer = (
        f"{_possessive(employee, is_self)} attendance for **{period.label}** "
        f"({period.describe()}): **{summary.get('present', 0)} day(s) present**"
        f", {summary.get('absent', 0)} absent"
        f", {summary.get('leave', 0)} on leave"
        f", {summary.get('official', 0)} on official work"
        f", {summary.get('holiday', 0)} holiday(s) and {summary.get('weekend', 0)} weekend day(s)"
        f" out of {len(days)} calendar day(s)."
    )

    if summary.get("late") or summary.get("early_out"):
        answer += (
            f" Arrival was late on **{summary.get('late', 0)}** day(s) and departure early on "
            f"**{summary.get('early_out', 0)}** day(s)."
        )
    elif working_days:
        answer += " No late arrivals or early departures were recorded."

    block = DataBlock(
        title=f"Attendance — {period.label}",
        columns=[
            Column(key="date", label="Date"),
            Column(key="checkin_time", label="Check In"),
            Column(key="checkout_time", label="Check Out"),
            Column(key="late_status", label="Arrival"),
            Column(key="early_status", label="Departure"),
            Column(key="status", label="Day Status"),
        ],
        rows=[
            {
                "date": row["date"],
                "checkin_time": row["checkin_time"] or "-",
                "checkout_time": row["checkout_time"] or "-",
                "late_status": row["late_status"],
                "early_status": row["early_status"],
                "status": row["status"],
            }
            for row in days
        ],
        summary={key: value for key, value in summary.items() if value},
    )

    return answer, block


# ------------------------------------------------------------ official work

def official_work(
    employee: Dict[str, Any], records: List[Dict[str, Any]], period: DateRange, is_self: bool
) -> Tuple[str, Optional[DataBlock]]:
    if not records:
        return (
            f"{_who(employee, is_self)} {'have' if is_self else 'has'} no official work records "
            f"for **{period.label}** ({period.describe()}).",
            None,
        )

    total = sum(
        ((record["end_date"] - record["start_date"]).days + 1)
        for record in records
        if record.get("start_date") and record.get("end_date")
    )

    answer = (
        f"{_who(employee, is_self)} {'have' if is_self else 'has'} **{len(records)} official work "
        f"record(s)** covering **{total} day(s)** in **{period.label}** ({period.describe()})."
    )

    block = DataBlock(
        title=f"Official work — {period.label}",
        columns=[
            Column(key="leave_type", label="Type"),
            Column(key="start_date", label="From"),
            Column(key="end_date", label="To"),
            Column(key="status", label="Status"),
            Column(key="reason", label="Purpose"),
        ],
        rows=[
            {
                "leave_type": record.get("leave_type") or "-",
                "start_date": _day(record.get("start_date")),
                "end_date": _day(record.get("end_date")),
                "status": (record.get("status") or "-").title(),
                "reason": record.get("reason") or "-",
            }
            for record in records
        ],
        summary={"records": len(records), "total_days": total},
    )

    return answer, block


# ---------------------------------------------------------------- profile

def profile(employee: Dict[str, Any], identity_name: str, is_admin: bool) -> Tuple[str, Optional[DataBlock]]:
    lines = [f"You are **{employee.get('name') or identity_name}**, ERP ID **{employee.get('erp_id')}**."]
    if employee.get("designation"):
        lines.append(f"Designation: {employee['designation']}.")
    if employee.get("section"):
        lines.append(f"Section: {employee['section']}.")
    if employee.get("grade"):
        lines.append(f"Grade: {employee['grade']}.")
    lines.append(
        "You are signed in as an administrator, so you can train new documents and look up "
        "other employees' records."
        if is_admin
        else "You are signed in as an employee, so I can show you your own leave and attendance."
    )
    return " ".join(lines), None


# --------------------------------------------------------------- smalltalk

def courtesy() -> str:
    return "Any time. Ask me again whenever you need a policy, a leave balance or an attendance report."


def greeting(name: str, is_admin: bool) -> str:
    """A greeting answers itself — no retrieval, no model call, no waiting."""
    first = (name or "").replace("Mr. ", "").replace("Ms. ", "").replace("Mrs. ", "").title()
    lines = [
        f"Hello {first.split()[0] if first else 'there'} — I am the ISMO HR Assistant. I can help with:",
        "",
        "- **HR policy** — anything in the HR Policies Manual, quoted with the page it came from.",
        "- **Your leave** — balance by leave type, and your leave records for any period.",
        "- **Your attendance** — check-in and check-out times, late arrivals, absences, day by day.",
        "- **Reports** — give me a date range and I will produce an Excel or PDF report.",
        "",
        'Try *"how many casual leaves do I have left"*, *"my attendance last month"*, '
        'or *"what is the medical leave policy"*.',
    ]
    if is_admin:
        lines.append("")
        lines.append(
            "As an administrator you can also train new documents with the paperclip button, "
            "and ask about another employee by name or ERP ID."
        )
    return "\n".join(lines)


# ----------------------------------------------------------------- reports

def report_offer(
    subject: str,
    employee: Dict[str, Any],
    period: DateRange,
    preferred_format: Optional[str] = None,
) -> ReportOffer:
    return ReportOffer(
        subject=subject,
        erp_id=employee["erp_id"],
        start=period.start,
        end=period.end,
        label=period.label,
        employee_name=employee.get("name"),
        preferred_format=preferred_format,
    )


def report_answer(
    subject: str,
    employee: Dict[str, Any],
    period: DateRange,
    row_count: int,
    is_self: bool,
    preferred_format: Optional[str],
) -> str:
    what = {"leave": "leave", "attendance": "attendance", "official_work": "official work"}[subject]
    whose = "your" if is_self else f"{employee.get('name')}'s"

    if row_count == 0 and subject != "attendance":
        empty = (
            f"There are no {what} records for {whose} account in **{period.label}** "
            f"({period.describe()}), so the report will be a nil return."
        )
        return (
            f"{empty} Preparing it as **{preferred_format.upper()}** now."
            if preferred_format
            else f"{empty} Would you still like it as **Excel** or **PDF**?"
        )

    if preferred_format:
        return (
            f"Preparing {whose} {what} report for **{period.label}** ({period.describe()}) as "
            f"**{preferred_format.upper()}** — {row_count} row(s). The download starts on its own; "
            "use the buttons below if you need it again or in the other format."
        )

    return (
        f"{whose.capitalize()} {what} report for **{period.label}** ({period.describe()}) is ready "
        f"— {row_count} row(s). Would you like it as **Excel** or **PDF**?"
    )
