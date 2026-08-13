from django.shortcuts import render
from django.http import JsonResponse, FileResponse
from django.conf import settings
from django.core.files.base import ContentFile
from .models import LeaveModel, LeaveTypeCountModel
from django.views.decorators.http import require_GET,require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
import json
import os
import uuid
from sqlalchemy import text, bindparam
from db import SessionLocal
from datetime import datetime,date,timedelta
from holidays.models import Holiday
from officialwork.models import OfficialWorkModel
from notifications.service import (
    notify_leave_decision,
    notify_leave_submitted,
)
from users.models import Employees
from addtouser.models import CustomUser
from django.contrib.auth.models import User

# Create your views here.

# Leave types restricted to a specific employee gender ("M"/"F")
GENDER_RESTRICTED_LEAVE_TYPES = {
    "maternity leave first": "F",
    "maternity leave second": "F",
    "maternity leave third": "F",
    "iddat leave": "F",
    "paternity leave": "M",
}

# Leave types that require a minimum number of years of service
MIN_SERVICE_YEARS_LEAVE_TYPES = {
    "hajj leave": 3,
}


def current_financial_year(today=None):
    """The Pakistan financial year containing `today`: 1 July -> 30 June.

    The same rule get_leaves_count and get_leave_balance apply inline; kept
    here so anything new shares one definition instead of another copy.
    """
    today = today or date.today()

    if today.month >= 7:
        return date(today.year, 7, 1), date(today.year + 1, 6, 30)
    return date(today.year - 1, 7, 1), date(today.year, 6, 30)


def get_employee_years_of_service(erp_id):
    """Returns years of service for an employee (based on their account's
    date_joined), or None if it cannot be determined."""
    authid = CustomUser.objects.filter(erpid=erp_id).values_list(
        "authid", flat=True
    ).first()
    if not authid:
        return None

    date_joined = User.objects.filter(pk=authid).values_list(
        "date_joined", flat=True
    ).first()
    if not date_joined:
        return None

    return (date.today() - date_joined.date()).days / 365.25

@require_GET
def get_leave_requests(request,erpid):
    leaves = LeaveModel.objects.all()
    data=[]
    sessions= SessionLocal()

    # The table shows the current financial year only. Overlap rather than
    # start_date alone, so a leave that straddles 30 June still appears in
    # both years it touches — the same rule the reports use.
    fy_start, fy_end = current_financial_year()

    query = text("""
        SELECT
            l.id,
            e.name AS employee_name,
            l.employee_id,
            l.erp_id,
            l.leave_type,
            l.head_erpid,
            (SELECT name FROM employees WHERE erp_id = l.head_erpid) AS headname,
            l.start_date,
            l.end_date,
            l.reason,
            l.status,
            l.created_at
        FROM leaves l
        LEFT JOIN employees e 
            ON l.erp_id = e.erp_id
        LEFT JOIN employees h
            ON l.head_erpid = h.erp_id
        WHERE e.flag = 1
          AND e.section_id = (SELECT section_id FROM employees WHERE erp_id = :epid)
          AND l.start_date IS NOT NULL
          AND l.end_date IS NOT NULL
          AND l.start_date <= :fy_end
          AND l.end_date >= :fy_start
        ORDER BY l.created_at DESC
    """)
    result = sessions.execute(
        query,
        {"epid": erpid, "fy_start": fy_start, "fy_end": fy_end},
    ).fetchall()

    # Attachment details come from the ORM so the download URL is built the
    # same way everywhere. One query for the whole page, not one per row.
    leave_ids = [row[0] for row in result]
    attachments = {
        leave.pk: attachment_payload(leave, request)
        for leave in LeaveModel.objects.filter(pk__in=leave_ids)
    } if leave_ids else {}
    no_attachment = {
        "has_attachment": False,
        "attachment_name": None,
        "attachment_url": None,
    }

    for row in result:
        data.append({
            "id": row[0],
            "employee_name": row[1],
            "employee_id": row[2],
            "erp_id": row[3],
            "leave_type": row[4],
            "start_date": row[7].strftime('%Y-%m-%d'),
            "end_date": row[8].strftime('%Y-%m-%d'),
            "reason": row[9],
            "status": row[10],
            "created_at": row[11].strftime('%Y-%m-%d %H:%M:%S'),
            "head_erpid": '-' if row[5]==0 else row[5],
            "head_name": row[6],
            **attachments.get(row[0], no_attachment),
        })
    sessions.close()
    return JsonResponse(
        {
            "leaves": data,
            # Returned so the table can state which year it is showing,
            # rather than looking as though older records were lost.
            "financial_year": {
                "start": fy_start.strftime("%d-%m-%Y"),
                "end": fy_end.strftime("%d-%m-%Y"),
                "label": f"{fy_start.year}-{fy_end.year}",
            },
        },
        status=200,
    )



@csrf_exempt
@require_POST
def get_leaves_count(request):
    data = json.loads(request.body.decode("utf-8"))

    erpid = data.get("erp_id", 0)
    section = data.get("section")

    sessions = SessionLocal()

    try:
        # -------------------------------------------------------
        # Pakistan Financial Year
        # 1 July  -> 30 June
        # -------------------------------------------------------
        today = date.today()

        if today.month >= 7:
            fy_start = date(today.year, 7, 1)
            fy_end = date(today.year + 1, 6, 30)
        else:
            fy_start = date(today.year - 1, 7, 1)
            fy_end = date(today.year, 6, 30)

        # -------------------------------------------------------
        # Employees
        # -------------------------------------------------------
        if erpid == 0 and section:

            employee_query = text("""
                SELECT
                    e.section_id,
                    e.erp_id,
                    e.name AS employee_name,
                    e.id AS employee_id,
                    s.name AS section_name
                FROM employees e
                LEFT JOIN sections s
                    ON s.id = e.section_id
                WHERE
                    e.flag = 1
                    AND e.section_id = :section
            """)

            employees = sessions.execute(
                employee_query,
                {"section": section}
            ).fetchall()

        else:

            employee_query = text("""
                SELECT
                    e.section_id,
                    e.erp_id,
                    e.name AS employee_name,
                    e.id AS employee_id,
                    s.name AS section_name
                FROM employees e
                LEFT JOIN sections s
                    ON s.id = e.section_id
                WHERE
                    e.flag = 1
                    AND e.section_id = :section
                    AND e.erp_id = :erpid
            """)

            employees = sessions.execute(
                employee_query,
                {
                    "section": section,
                    "erpid": erpid
                }
            ).fetchall()

        result = []

        for emp in employees:

            leave_count = 0

            # -------------------------------------------------------
            # Normal Leaves
            # -------------------------------------------------------
            leaves = sessions.execute(
                text("""
                    SELECT
                        start_date,
                        end_date
                    FROM leaves
                    WHERE
                        erp_id = :erp_id
                        AND status='approved'
                """),
                {"erp_id": emp.erp_id}
            ).fetchall()

            for leave in leaves:

                if not leave.start_date or not leave.end_date:
                    continue

                overlap_start = max(leave.start_date, fy_start)
                overlap_end = min(leave.end_date, fy_end)

                if overlap_start <= overlap_end:
                    leave_count += (overlap_end - overlap_start).days + 1

            # -------------------------------------------------------
            # Official Work Leaves
            # -------------------------------------------------------
            official_leaves = sessions.execute(
                text("""
                    SELECT
                        start_date,
                        end_date
                    FROM official_work_leaves
                    WHERE
                        erp_id = :erp_id
                        AND status='approved'
                """),
                {"erp_id": emp.erp_id}
            ).fetchall()

            for leave in official_leaves:

                if not leave.start_date or not leave.end_date:
                    continue

                overlap_start = max(leave.start_date, fy_start)
                overlap_end = min(leave.end_date, fy_end)

                if overlap_start <= overlap_end:
                    leave_count += (overlap_end - overlap_start).days + 1

            result.append({
                "id": emp.employee_id,
                "employee_id": emp.employee_id,
                "employee_name": emp.employee_name,
                "section": emp.section_name,
                "erp_id": emp.erp_id,
                "financial_year": f"{fy_start.strftime('%d-%b-%Y')} to {fy_end.strftime('%d-%b-%Y')}",
                "leave_count": leave_count
            })

        return JsonResponse({"attendance": result}, status=200)

    finally:
        sessions.close()

# "Official Work" is not a row in the `leaves` table — it is its own module
# backed by `official_work_leaves`, where each record carries one of several
# sub-types (Meetings, Official Tour, Work From Home, ...). Selecting
# "Official Work" on a leave report therefore has to read from that table
# instead, otherwise the report comes back empty (or worse, shows only the
# handful of legacy rows that were typed into `leaves` by hand).
OFFICIAL_WORK_LEAVE_TYPE = "Official Work"


def get_official_work_records(
    session,
    section_id,
    start_date,
    end_date,
    include_pending,
    erp_id=None,
):
    """Return one row per official-work record overlapping the date range.

    Reads BOTH sources and unions them:

    * `official_work_leaves` — the official work module, where every new
      entry is recorded. Each row carries a sub-type (Meetings, Official
      Tour, Work From Home, ...).
    * `leaves` where leave_type = 'Official Work' — historical entries made
      through the leave application form before official work moved to its
      own module. The form no longer offers the option, but these rows still
      exist and must keep showing up or the report would under-report.

    Each record is tagged with `source` so a reader can tell which table it
    came from. `include_pending` mirrors whatever status filter the calling
    report already applies to ordinary leaves, so the official-work detail
    agrees with the summary shown above it on the same page.
    """
    # Statuses are internal constants, never user input — safe to inline.
    status_clause = (
        "IN ('approved', 'pending')" if include_pending else "= 'approved'"
    )
    erp_clause = "AND r.erp_id = :erp_id" if erp_id else ""

    # UNION ALL, not UNION: two genuinely separate records that happen to
    # share every column are still two records, and the day-level dedupe in
    # summarize_official_work handles any overlap in the totals.
    records_query = text(f"""
        SELECT
            r.erp_id,
            e.name AS employee_name,
            s.name AS section_name,
            r.leave_type,
            r.start_date,
            r.end_date,
            r.status,
            r.reason,
            r.source
        FROM (
            SELECT
                o.erp_id, o.leave_type, o.start_date, o.end_date,
                o.status, o.reason,
                'Official work module' AS source
            FROM official_work_leaves o

            UNION ALL

            SELECT
                l.erp_id, l.leave_type, l.start_date, l.end_date,
                l.status, l.reason,
                'Leave form (historical)' AS source
            FROM leaves l
            WHERE l.leave_type = :official_work_type
        ) r
        INNER JOIN employees e ON e.erp_id = r.erp_id
        LEFT JOIN sections s ON s.id = e.section_id
        WHERE e.flag = 1
          AND e.section_id = :section
          AND r.start_date <= :end_date
          AND r.end_date >= :start_date
          AND LOWER(r.status) {status_clause}
          {erp_clause}
        ORDER BY r.start_date DESC, e.name
    """)

    params = {
        "section": section_id,
        "start_date": start_date,
        "end_date": end_date,
        "official_work_type": OFFICIAL_WORK_LEAVE_TYPE,
    }
    if erp_id:
        params["erp_id"] = erp_id

    rows = session.execute(records_query, params).fetchall()

    records = []
    for row in rows:
        # Clip to the requested window so a tour that straddles the boundary
        # is not counted beyond it — same rule the leave counts use.
        days = clipped_days(row.start_date, row.end_date, start_date, end_date)
        if not days:
            continue

        records.append({
            "erp_id": row.erp_id,
            "employee_name": row.employee_name,
            "section": row.section_name,
            "leave_type": row.leave_type,
            "start_date": row.start_date.strftime("%d-%m-%Y"),
            "end_date": row.end_date.strftime("%d-%m-%Y"),
            "days": len(days),
            "status": row.status,
            "reason": row.reason,
            "source": row.source,
            # Consumed by summarize_official_work, stripped before responding.
            "_days": days,
        })

    return records


def official_work_day_sets(records):
    """Distinct official-work days per ERP ID, across both source tables.

    Lets the per-employee summary agree with the record list underneath it:
    a day recorded once in the official work module and again as a legacy
    leave row is one day off, not two.
    """
    days_by_erp = {}
    for record in records:
        days_by_erp.setdefault(record["erp_id"], set()).update(record["_days"])
    return days_by_erp


def fetch_official_work_module_rows(
    session, erp_id, range_start, range_end, include_pending=False
):
    """Official work module rows for one employee, for the detail reports.

    Those reports walk the `leaves` table per leave type, which on its own
    would show nothing but the historical 'Official Work' entries. This adds
    the module's own records so the two sources are reported together.
    """
    status_clause = (
        "IN ('approved', 'pending')" if include_pending else "= 'approved'"
    )

    return session.execute(
        text(f"""
            SELECT leave_type, start_date, end_date, reason, status
            FROM official_work_leaves
            WHERE erp_id = :erp_id
              AND LOWER(status) {status_clause}
              AND start_date <= :range_end
              AND end_date >= :range_start
            ORDER BY start_date ASC
        """),
        {
            "erp_id": erp_id,
            "range_start": range_start,
            "range_end": range_end,
        },
    ).fetchall()


def is_official_work(leave_type):
    return (leave_type or "").strip().lower() == OFFICIAL_WORK_LEAVE_TYPE.lower()


# ==========================================================================
# Medical / sick leave attachments
# ==========================================================================

# Leave types that may carry a supporting medical document. Matched
# case-insensitively; "Sick Leave" is included because some sections use that
# wording even though the configured type is "Medical Leave".
MEDICAL_LEAVE_TYPES = {"medical leave", "sick leave"}


def allows_attachment(leave_type):
    return (leave_type or "").strip().lower() in MEDICAL_LEAVE_TYPES


def build_attachment_name(original_name):
    """A random storage name that keeps only the extension.

    Medical filenames routinely contain the patient's name and the clinic, so
    the uploaded name is never used on disk — it is kept in a separate column
    for display and the stored file gets an unguessable name instead.
    """
    extension = os.path.splitext(original_name or "")[1].lower()
    return f"{uuid.uuid4().hex}{extension}"


def validate_attachment(upload, leave_type):
    """Returns an error string, or None when the upload is acceptable."""
    if upload is None:
        return None

    if not allows_attachment(leave_type):
        return (
            "Attachments are only accepted for medical or sick leave."
        )

    extension = os.path.splitext(upload.name or "")[1].lower()
    allowed = [
        ext.lower()
        for ext in getattr(settings, "LEAVE_ATTACHMENT_ALLOWED_EXTENSIONS", [])
    ]
    if allowed and extension not in allowed:
        return (
            "Unsupported file type. Allowed: " + ", ".join(sorted(allowed))
        )

    max_mb = getattr(settings, "LEAVE_ATTACHMENT_MAX_MB", 5)
    if upload.size > max_mb * 1024 * 1024:
        return f"Attachment must be {max_mb} MB or smaller."

    return None


def attachment_payload(leave, request=None):
    """Attachment fields for a leave row, or empty values when there is none.

    `has_attachment` lets the record table render a View link without having
    to reason about whether the URL is usable.
    """
    name = getattr(leave, "attachment", None)
    if not name:
        return {
            "has_attachment": False,
            "attachment_name": None,
            "attachment_url": None,
        }

    path = f"/api/leaves/attachment/{leave.pk}/"
    return {
        "has_attachment": True,
        "attachment_name": (
            getattr(leave, "attachment_original_name", None)
            or os.path.basename(str(name))
        ),
        # Absolute so the frontend never has to derive a media host.
        "attachment_url": (
            request.build_absolute_uri(path) if request is not None else path
        ),
    }


@require_GET
def download_leave_attachment(request, leave_id):
    """Stream a leave attachment.

    Routed through a view rather than exposed under MEDIA_URL so the stored
    filename stays unguessable and access can be restricted here later — see
    the note in the handover: these are medical records and this project's API
    currently has no authentication layer to hook into.
    """
    leave = LeaveModel.objects.filter(pk=leave_id).first()
    if leave is None or not leave.attachment:
        return JsonResponse({"error": "Attachment not found"}, status=404)

    try:
        handle = leave.attachment.open("rb")
    except (FileNotFoundError, ValueError):
        # Row references a file that is no longer on disk.
        return JsonResponse({"error": "Attachment file is missing"}, status=404)

    display_name = (
        leave.attachment_original_name
        or os.path.basename(leave.attachment.name)
    )
    response = FileResponse(handle, as_attachment=False)
    # Quotes escaped so a filename containing one cannot break the header.
    safe_name = display_name.replace('"', "")
    response["Content-Disposition"] = f'inline; filename="{safe_name}"'
    return response


def strip_internal_fields(records):
    """Drop the day-set scratch field before the records go over the wire."""
    return [
        {key: value for key, value in record.items() if not key.startswith("_")}
        for record in records
    ]


def summarize_official_work(records):
    """Totals per official-work sub-type, for the summary strip.

    Day totals count each calendar day once per employee. The live data holds
    overlapping official-work records (e.g. a tour recorded twice), so summing
    each record's span would report more days than actually elapsed.
    """
    totals = {}
    seen_days = {}

    for record in records:
        label = record["leave_type"] or "Unspecified"
        bucket = totals.setdefault(
            label, {"leave_type": label, "records": 0, "days": 0}
        )
        bucket["records"] += 1

        # Distinct (employee, day) pairs per sub-type.
        day_set = seen_days.setdefault(label, set())
        for day in record["_days"]:
            day_set.add((record["erp_id"], day))

    for label, day_set in seen_days.items():
        totals[label]["days"] = len(day_set)

    return sorted(totals.values(), key=lambda item: -item["days"])


# ==========================================================================
# Shared reporting core
#
# Both leave reports previously counted days by summing each leave record's
# span. That is wrong whenever two records for the same employee and type
# overlap — and the live data contains 27 such pairs, including exact
# duplicates (one employee has the same 10-day Earned Leave entered twice,
# which reported 20 days). Counting *distinct calendar days* instead makes a
# duplicate or partial overlap contribute the days it actually covers.
#
# The old loops also issued three queries per employee. These helpers fetch
# every employee's rows in one pass, so a 182-person section costs a fixed
# handful of queries rather than several hundred.
# ==========================================================================

def parse_report_range(start_date, end_date):
    """Parse and sanity-check the requested window.

    Returns (start, end, error_message).
    """
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None, None, "start_date and end_date must be YYYY-MM-DD"

    if start > end:
        return None, None, "start_date must be on or before end_date"

    return start, end, None


def clipped_days(row_start, row_end, range_start, range_end):
    """Every calendar day of a record that falls inside the window.

    Returns an empty list for records that cannot be counted — missing dates,
    or an end before the start. The live data holds two such rows (one
    Maternity Leave runs 2025-12-09 to 2025-04-08); the old individual report
    had no guard and let that subtract ~245 days from the employee's total.
    """
    if row_start is None or row_end is None or row_end < row_start:
        return []

    first = max(row_start, range_start)
    last = min(row_end, range_end)
    if first > last:
        return []

    return [first + timedelta(days=offset)
            for offset in range((last - first).days + 1)]


def fetch_section_employees(session, section_id, erp_id=None):
    """Active employees of a section, one row per ERP ID.

    The employees table currently holds a duplicated active record (ERP 805
    appears twice), which made that person show up twice in every report.
    """
    erp_clause = "AND e.erp_id = :erp_id" if erp_id else ""

    rows = session.execute(
        text(f"""
            SELECT
                e.id AS employee_id,
                e.erp_id,
                e.name AS employee_name,
                s.name AS section_name
            FROM employees e
            LEFT JOIN sections s ON e.section_id = s.id
            WHERE e.flag = 1
              AND e.section_id = :section
              {erp_clause}
            ORDER BY e.name, e.id
        """),
        {"section": section_id, **({"erp_id": erp_id} if erp_id else {})},
    ).fetchall()

    employees = []
    seen = set()
    duplicates = 0
    for row in rows:
        if row.erp_id in seen:
            duplicates += 1
            continue
        seen.add(row.erp_id)
        employees.append(row)

    return employees, duplicates


def fetch_leave_days(
    session, erp_ids, leave_type, include_pending, range_start, range_end
):
    """Distinct leave days per ERP ID, in a single query.

    Returns (days_by_erp, quality) where days_by_erp maps erp_id -> set of
    dates and quality reports what the data forced us to drop or merge.
    """
    quality = {"records_read": 0, "records_skipped": 0, "overlapping_days_merged": 0}
    if not erp_ids:
        return {}, quality

    statuses = ["approved", "pending"] if include_pending else ["approved"]

    query = text("""
        SELECT erp_id, start_date, end_date
        FROM leaves
        WHERE erp_id IN :erp_ids
          AND LOWER(status) IN :statuses
          AND leave_type = :leave_type
          AND start_date <= :range_end
          AND end_date >= :range_start
    """).bindparams(
        bindparam("erp_ids", expanding=True),
        bindparam("statuses", expanding=True),
    )

    rows = session.execute(
        query,
        {
            "erp_ids": list(erp_ids),
            "statuses": statuses,
            "leave_type": leave_type,
            "range_start": range_start,
            "range_end": range_end,
        },
    ).fetchall()

    days_by_erp = {}
    for row in rows:
        quality["records_read"] += 1
        days = clipped_days(row.start_date, row.end_date, range_start, range_end)
        if not days:
            quality["records_skipped"] += 1
            continue

        bucket = days_by_erp.setdefault(row.erp_id, set())
        before = len(bucket)
        bucket.update(days)
        # Anything that did not enlarge the set was already claimed by another
        # record — i.e. a duplicate or overlapping entry.
        quality["overlapping_days_merged"] += len(days) - (len(bucket) - before)

    return days_by_erp, quality


def fetch_leave_allocation(session, leave_type):
    """Annual allocation for a leave type — one lookup, not one per employee."""
    row = session.execute(
        text("""
            SELECT total_leaves
            FROM leave_type_counts
            WHERE leave_type = :leave_type
        """),
        {"leave_type": leave_type},
    ).fetchone()

    return row[0] if row is not None else None


def fetch_rr_erp_ids(session, erp_ids, include_pending, range_start, range_end):
    """ERP IDs with Rest & Recreational leave in the window.

    Casual leave is charged an extra 10 days for these employees (the rule
    get_leave_balance already applies). Fetched set-wise rather than with a
    per-employee ORM round trip.
    """
    if not erp_ids:
        return set()

    statuses = ["approved", "pending"] if include_pending else ["approved"]

    query = text("""
        SELECT DISTINCT erp_id
        FROM leaves
        WHERE erp_id IN :erp_ids
          AND leave_type = 'Rest & Recreational Leave'
          AND LOWER(status) IN :statuses
          AND start_date <= :range_end
          AND end_date >= :range_start
    """).bindparams(
        bindparam("erp_ids", expanding=True),
        bindparam("statuses", expanding=True),
    )

    rows = session.execute(
        query,
        {
            "erp_ids": list(erp_ids),
            "statuses": statuses,
            "range_start": range_start,
            "range_end": range_end,
        },
    ).fetchall()

    return {row.erp_id for row in rows}


def build_report_metadata(
    leave_type, range_start, range_end, include_pending, quality, duplicates
):
    """Self-describing footer so a reader can audit what the numbers mean."""
    notes = []
    if quality.get("records_skipped"):
        notes.append(
            f"{quality['records_skipped']} record(s) ignored: end date before "
            "start date, or missing dates."
        )
    if quality.get("overlapping_days_merged"):
        notes.append(
            f"{quality['overlapping_days_merged']} duplicate/overlapping day(s) "
            "counted once."
        )
    if duplicates:
        notes.append(
            f"{duplicates} duplicate employee record(s) collapsed by ERP ID."
        )

    return {
        "leave_type": leave_type,
        "start_date": range_start.strftime("%d-%m-%Y"),
        "end_date": range_end.strftime("%d-%m-%Y"),
        "statuses_counted": (
            ["approved", "pending"] if include_pending else ["approved"]
        ),
        "counting_method": "distinct calendar days within the selected range",
        "records_read": quality.get("records_read", 0),
        "data_quality_notes": notes,
    }


@require_GET
def get_leave_types(request):
    """The configured leave types, for report filters.

    The report pages used to hard-code their own lists, which had drifted from
    the master table: the section report offered "Sick Leave" and both offered
    a plain "Maternity Leave", none of which exist in leave_type_counts — so
    picking them could only ever return an empty report. Official Work is
    appended because it is a real filter option backed by its own table.
    """
    session = SessionLocal()
    try:
        rows = session.execute(text("""
            SELECT leave_type, total_leaves
            FROM leave_type_counts
            WHERE leave_type IS NOT NULL AND LTRIM(RTRIM(leave_type)) <> ''
            ORDER BY leave_type
        """)).fetchall()

        types = [
            {"leave_type": row[0], "total_leaves": row[1]}
            for row in rows
        ]

        if not any(t["leave_type"] == OFFICIAL_WORK_LEAVE_TYPE for t in types):
            types.append(
                {"leave_type": OFFICIAL_WORK_LEAVE_TYPE, "total_leaves": None}
            )

        return JsonResponse({"leave_types": types}, status=200)
    finally:
        session.close()


@csrf_exempt
@require_POST
def individual_report(request):
    data = json.loads(request.body.decode("utf-8"))
    
    erpid = data.get("erp_id", 0)
    section = data.get("section")
    leave_type = data.get("leave_type")   # REQUIRED
    start_date = data.get("start_date")
    end_date = data.get("end_date")

    # Validate required fields
    if not all([section, leave_type, start_date, end_date]):
        return JsonResponse(
            {"error": "section, leave_type, start_date, and end_date are required"},
            status=400
        )

    start_date, end_date, range_error = parse_report_range(start_date, end_date)
    if range_error:
        return JsonResponse({"error": range_error}, status=400)

    # A leave only counts once it is approved. Pending applications are
    # excluded from both `leave_count` and `remaining_leaves`, so an
    # application awaiting a decision does not consume a balance it may never
    # use. All the leave reports now agree on this — see section_leave_report,
    # individual_detail_report and leavetype_detail_report.
    include_pending = False

    sessions = SessionLocal()

    try:
        employees, duplicate_employees = fetch_section_employees(
            sessions, section, erpid or None
        )
        erp_ids = [emp.erp_id for emp in employees]

        # Three set-based queries replace the previous three-per-employee.
        days_by_erp, quality = fetch_leave_days(
            sessions, erp_ids, leave_type, include_pending, start_date, end_date
        )
        total_leaves = fetch_leave_allocation(sessions, leave_type)
        rr_erp_ids = (
            fetch_rr_erp_ids(
                sessions, erp_ids, include_pending, start_date, end_date
            )
            if leave_type.lower() == "casual leave"
            else set()
        )

        # Official work spans two tables, so its records are fetched first and
        # the per-employee counts are derived from that union — otherwise the
        # summary would report only the historical `leaves` rows while the
        # breakdown underneath listed both sources.
        official_work = []
        if leave_type == OFFICIAL_WORK_LEAVE_TYPE:
            official_work = get_official_work_records(
                sessions,
                section,
                start_date,
                end_date,
                include_pending=include_pending,
                erp_id=erpid or None,
            )
            days_by_erp = official_work_day_sets(official_work)

        result = []
        for emp in employees:
            leave_count = len(days_by_erp.get(emp.erp_id, ()))

            # Taking Rest & Recreational leave costs an extra 10 casual days
            # (the same rule get_leave_balance applies).
            if emp.erp_id in rr_erp_ids:
                leave_count += 10

            remaining_leaves = (
                total_leaves - leave_count if total_leaves is not None else None
            )

            result.append({
                "employee_id": emp.employee_id,
                "erp_id": emp.erp_id,
                "employee_name": emp.employee_name,
                "section": emp.section_name,
                "leave_type": leave_type,
                "leave_count": leave_count,
                "remaining_leaves": remaining_leaves,
                "start_date": start_date.strftime("%d-%m-%Y"),
                "end_date": end_date.strftime("%d-%m-%Y"),
            })

        return JsonResponse(
            {
                "attendance": result,
                "official_work": strip_internal_fields(official_work),
                "official_work_summary": summarize_official_work(official_work),
                "report_meta": build_report_metadata(
                    leave_type,
                    start_date,
                    end_date,
                    include_pending,
                    quality,
                    duplicate_employees,
                ),
            },
            status=200,
        )

    finally:
        sessions.close()

@csrf_exempt
@require_POST
def individual_detail_report(request):
    data = json.loads(request.body.decode("utf-8"))
    
    erpid = data.get("erp_id", 0)
    section = data.get("section")
    start_date = data.get("start_date")
    end_date = data.get("end_date")
   
    # Validate required fields
    if not all([section, start_date, end_date]):
        return JsonResponse(
            {"error": "section, start_date, and end_date are required"},
            status=400
        )

    # Convert dates to Python date objects
    start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

    sessions = SessionLocal()

    # Fetch employee
    if erpid == 0:
        query = text(""" 
            SELECT e.id, e.erp_id, e.name, s.name, e.gender
            FROM employees e
            LEFT JOIN sections s ON e.section_id = s.id
            WHERE e.flag = 1 AND e.section_id = :section
        """)
        emp = sessions.execute(query, {"section": section}).fetchone()
    else:
        query = text(""" 
            SELECT e.id, e.erp_id, e.name, s.name, e.gender
            FROM employees e
            LEFT JOIN sections s ON e.section_id = s.id
            WHERE e.flag = 1 AND e.section_id = :section AND e.erp_id = :erp_id
        """)
        emp = sessions.execute(query, {"section": section, "erp_id": erpid}).fetchone()

    if not emp:
        sessions.close()
        return JsonResponse({"error": "Employee not found"}, status=404)

    # Eligibility inputs: an employee's gender and years of service decide
    # which leave types they are even entitled to apply for.
    employee_gender = (emp[4] or "").upper()
    years_of_service = get_employee_years_of_service(emp[1])

    # Casual leave is charged an extra 10 days whenever the employee has taken
    # Rest & Recreational leave in the period. Only an *approved* R&R leave
    # triggers the charge, matching the approved-only rule below.
    has_rr_leave = LeaveModel.objects.filter(
        erp_id=emp[1],
        leave_type="Rest & Recreational Leave",
        start_date__lte=end_date,
        end_date__gte=start_date,
        status__iexact="approved",
    ).exists()

    # Master list of every configured leave type with its annual allocation.
    all_types = sessions.execute(text("""
        SELECT leave_type, total_leaves
        FROM leave_type_counts
        ORDER BY leave_type
    """)).fetchall()

    # Approved only: a pending application is not a taken leave.
    filtered_leaves_query = text("""
        SELECT start_date, end_date
        FROM leaves
        WHERE erp_id = :erp_id
          AND LOWER(status) = 'approved'
          AND leave_type = :leave_type
          AND start_date <= :end_date
          AND end_date >= :start_date
    """)

    # Official work also lives in its own table, so its day count is the union
    # of the module's records and the historical 'Official Work' rows in
    # `leaves`. Fetched once rather than inside the per-type loop.
    official_work_module_days = set()
    if any(is_official_work(row[0]) for row in all_types):
        for ow_row in fetch_official_work_module_rows(
            sessions, emp[1], start_date, end_date, include_pending=False
        ):
            official_work_module_days.update(
                clipped_days(ow_row[1], ow_row[2], start_date, end_date)
            )

    result = []

    # Walk every leave type so the report reflects the employee's *overall*
    # standing — the types availed and the ones not availed yet — while
    # skipping the types this particular employee is not eligible for.
    for type_row in all_types:
        leave_type = type_row[0]
        total_leaves = type_row[1]
        lt_lower = (leave_type or "").lower()

        # Gender-restricted types (e.g. maternity / paternity / iddat).
        required_gender = GENDER_RESTRICTED_LEAVE_TYPES.get(lt_lower)
        if required_gender and employee_gender != required_gender:
            continue

        # Types needing a minimum tenure (e.g. hajj leave).
        required_service_years = MIN_SERVICE_YEARS_LEAVE_TYPES.get(lt_lower)
        if required_service_years and (
            years_of_service is None or years_of_service < required_service_years
        ):
            continue

        # Days availed for this type within the reporting window.
        leaves = sessions.execute(
            filtered_leaves_query,
            {
                "erp_id": emp[1],
                "leave_type": leave_type,
                "start_date": start_date,
                "end_date": end_date,
            },
        ).fetchall()

        # Distinct days, so a duplicated or overlapping entry is not counted
        # twice and a row with its dates reversed cannot subtract days.
        day_set = set()
        for leave in leaves:
            day_set.update(clipped_days(leave[0], leave[1], start_date, end_date))

        # Fold in the official work module's own records for that type.
        if is_official_work(leave_type):
            day_set |= official_work_module_days

        leave_count = len(day_set)

        if lt_lower == "casual leave" and has_rr_leave:
            leave_count += 10

        remaining_leaves = (
            total_leaves - leave_count if total_leaves is not None else None
        )

        # Three-state standing for the category:
        #   Not Availed        -> none of the allocation used
        #   Availed            -> the whole allocation used up (nothing left)
        #   Partially Availed  -> some used, but a balance still remains
        if leave_count <= 0:
            status = "Not Availed"
        elif total_leaves is not None and leave_count >= total_leaves:
            status = "Availed"
        else:
            status = "Partially Availed"

        result.append({
            "employee_id": emp[0],
            "erp_id": emp[1],
            "employee_name": emp[2],
            "section": emp[3],
            "leave_type": leave_type,
            "total_leaves": total_leaves,
            "leave_count": leave_count,
            "remaining_leaves": remaining_leaves,
            "availed": leave_count > 0,
            "status": status,
            "start_date": start_date.strftime("%d-%m-%Y"),
            "end_date": end_date.strftime("%d-%m-%Y"),
        })

    sessions.close()
    return JsonResponse({"attendance": result}, status=200)


@csrf_exempt
@require_POST
def leavetype_detail_report(request):
    data = json.loads(request.body.decode("utf-8"))
    
    erp_id = data.get("erp_id", 0)
    section = data.get("section")
    leave_type = data.get("leavetype")
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    
    # Validate required fields
    if not all([section, leave_type, start_date, end_date]):
        return JsonResponse(
            {"error": "section, leave_type, start_date, and end_date are required"},
            status=400
        )
    print(data)
    # Convert dates to Python date objects
    start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

    sessions = SessionLocal()

    # Fetch employees
    if erp_id == 0:
        query = text(""" 
            SELECT e.id, e.erp_id, e.name, s.name, e.gender
            FROM employees e
            LEFT JOIN sections s ON e.section_id = s.id
            WHERE e.flag = 1 AND e.section_id = :section
        """)
        employees = sessions.execute(query, {"section": section}).fetchall()
    else:
        query = text(""" 
            SELECT e.id, e.erp_id, e.name, s.name, e.gender
            FROM employees e
            LEFT JOIN sections s ON e.section_id = s.id
            WHERE e.flag = 1 AND e.section_id = :section AND e.erp_id = :erp_id
        """)
        employees = sessions.execute(query, {"section": section, "erp_id": erp_id}).fetchall()

    if not employees:
        print("No employees found")
        sessions.close()
        return JsonResponse({"error": "Employee not found"}, status=404)

    result = []

    # Process each employee
    for emp in employees:
        # Get all leaves of specific type for this employee in date range
        # Approved only: a pending application is not a taken leave.
        leaves_query = text("""
            SELECT id, start_date, end_date, reason, status
            FROM leaves
            WHERE erp_id = :erp_id
              AND leave_type = :leave_type
              AND LOWER(status) = 'approved'
              AND start_date <= :end_date
              AND end_date >= :start_date
            ORDER BY start_date ASC
        """)
        
        leaves = sessions.execute(
            leaves_query,
            {
                "erp_id": emp[1], 
                "leave_type": leave_type,
                "start_date": start_date, 
                "end_date": end_date
            }
        ).fetchall()
        # Process each leave record
        for leave in leaves:
            days = clipped_days(leave[1], leave[2], start_date, end_date)
            if not days:
                continue

            result.append({
                "erp_id": emp[1],
                "employee_name": emp[2],
                "section": emp[3],
                "start_date": leave[1].strftime("%Y-%m-%d"),
                "end_date": leave[2].strftime("%Y-%m-%d"),
                "leave_type": leave_type,
                "leave_count": len(days),
                "source": "Leave form (historical)",
            })

        # Official work is also recorded in its own module, so a search for it
        # has to list those records too — the `leaves` table only holds the
        # historical entries made before the module existed.
        if is_official_work(leave_type):
            for ow_row in fetch_official_work_module_rows(
                sessions, emp[1], start_date, end_date, include_pending=False
            ):
                days = clipped_days(ow_row[1], ow_row[2], start_date, end_date)
                if not days:
                    continue

                result.append({
                    "erp_id": emp[1],
                    "employee_name": emp[2],
                    "section": emp[3],
                    "start_date": ow_row[1].strftime("%Y-%m-%d"),
                    "end_date": ow_row[2].strftime("%Y-%m-%d"),
                    # The module's own sub-type (Meetings, Official Tour, ...).
                    "leave_type": ow_row[0] or leave_type,
                    "leave_count": len(days),
                    "source": "Official work module",
                })

    sessions.close()
    return JsonResponse({"attendance": result}, status=200)


@csrf_exempt
@require_POST
def section_leave_report(request):
    data = json.loads(request.body.decode("utf-8"))

    section_id = data.get("section")
    leave_type = data.get("leave_type")
    start_date = data.get("start_date")
    end_date = data.get("end_date")

    if not all([section_id, leave_type, start_date, end_date]):
        return JsonResponse(
            {
                "error": "section, leave_type, start_date and end_date are required"
            },
            status=400
        )

    start_date, end_date, range_error = parse_report_range(start_date, end_date)
    if range_error:
        return JsonResponse({"error": range_error}, status=400)

    # This report shows leave actually granted, so pending applications are
    # excluded. The individual report counts them — see individual_report.
    include_pending = False

    session = SessionLocal()

    try:
        employees, duplicate_employees = fetch_section_employees(
            session, section_id
        )
        erp_ids = [emp.erp_id for emp in employees]

        # One query for the whole section instead of one per employee.
        days_by_erp, quality = fetch_leave_days(
            session, erp_ids, leave_type, include_pending, start_date, end_date
        )

        # Official work spans the official work module and the historical
        # 'Official Work' rows in `leaves`, so its counts come from the union
        # of both — see get_official_work_records.
        official_work = []
        if leave_type == OFFICIAL_WORK_LEAVE_TYPE:
            official_work = get_official_work_records(
                session,
                section_id,
                start_date,
                end_date,
                include_pending=include_pending,
            )
            days_by_erp = official_work_day_sets(official_work)

        result = []
        for emp in employees:
            leave_count = len(days_by_erp.get(emp.erp_id, ()))

            # Only return employees having selected leave
            if leave_count > 0:
                result.append({
                    "employee_id": emp.employee_id,
                    "erp_id": emp.erp_id,
                    "employee_name": emp.employee_name,
                    "section": emp.section_name,
                    "leave_type": leave_type,
                    "leave_count": leave_count,
                    "start_date": start_date.strftime("%d-%m-%Y"),
                    "end_date": end_date.strftime("%d-%m-%Y"),
                })

        return JsonResponse(
            {
                "attendance": result,
                "official_work": strip_internal_fields(official_work),
                "official_work_summary": summarize_official_work(official_work),
                "report_meta": build_report_metadata(
                    leave_type,
                    start_date,
                    end_date,
                    include_pending,
                    quality,
                    duplicate_employees,
                ),
            },
            status=200,
        )

    finally:
        session.close()

@csrf_exempt
@require_POST
def get_leave_balance(request):
    data = json.loads(request.body.decode("utf-8"))

    erp_id = data.get("erp_id")
    leave_type = data.get("leave_type")

    if not erp_id or not leave_type:
        return JsonResponse(
            {"error": "erp_id and leave_type are required"},
            status=400
        )

    # -------------------------------------------------------
    # Pakistan Financial Year
    # 1 July  -> 30 June
    # -------------------------------------------------------
    today = date.today()

    if today.month >= 7:
        fy_start = date(today.year, 7, 1)
        fy_end = date(today.year + 1, 6, 30)
    else:
        fy_start = date(today.year - 1, 7, 1)
        fy_end = date(today.year, 6, 30)

    leave_limit = LeaveTypeCountModel.objects.filter(leave_type=leave_type).first()
    total_allowed = leave_limit.total_leaves if leave_limit else None

    used_leaves = LeaveModel.objects.filter(
        erp_id=erp_id,
        leave_type=leave_type,
        status__in=["approved", "pending"],
        start_date__lte=fy_end,
        end_date__gte=fy_start,
    )

    used_days = 0
    for leave in used_leaves:
        if leave.start_date and leave.end_date:
            actual_start = max(leave.start_date, fy_start)
            actual_end = min(leave.end_date, fy_end)
            used_days += (actual_end - actual_start).days + 1

    if leave_type.lower() == "casual leave":
        has_rr_leave = LeaveModel.objects.filter(
            erp_id=erp_id,
            leave_type="Rest & Recreational Leave",
            status__in=["approved", "pending"],
            start_date__lte=fy_end,
            end_date__gte=fy_start,
        ).exists()

        if has_rr_leave:
            used_days += 10

    remaining_leaves = total_allowed - used_days if total_allowed is not None else None

    return JsonResponse(
        {
            "leave_type": leave_type,
            "total_allowed": total_allowed,
            "used_days": used_days,
            "remaining_leaves": remaining_leaves,
            "financial_year": f"{fy_start.strftime('%d-%b-%Y')} to {fy_end.strftime('%d-%b-%Y')}",
        },
        status=200
    )


@csrf_exempt
@require_POST
def create_leave_request(request):
    try:
        # The form posts multipart/form-data when a medical record is attached
        # and JSON otherwise, so accept both.
        upload = None
        if request.content_type and request.content_type.startswith(
            "multipart/form-data"
        ):
            data = {key: value for key, value in request.POST.items()}
            upload = request.FILES.get("attachment")
        else:
            data = json.loads(request.body.decode("utf-8"))

        erp_id = data.get("erp_id")
        employee_id = data.get("employee_id")
        leave_type = data.get("leave_type")
        start_date = data.get("start_date")
        end_date = data.get("end_date")

        # --------------------------------------------------
        # REQUIRED FIELDS CHECK
        # --------------------------------------------------
        if not all([erp_id, employee_id, leave_type, start_date, end_date]):
            return JsonResponse(
                {"error": "erp_id, employee_id, leave_type, start_date and end_date are required"},
                status=400
            )

        # --------------------------------------------------
        # OFFICIAL WORK IS NO LONGER A LEAVE TYPE
        # --------------------------------------------------
        # It has its own module and its own table. The leave form no longer
        # offers the option; this rejects it server side too, so no new
        # 'Official Work' rows can land in `leaves` by any route. Existing
        # historical rows are left untouched and still appear in the reports.
        if is_official_work(leave_type):
            return JsonResponse(
                {
                    "error": (
                        "Official Work is no longer applied for through the "
                        "leave form. Please use the Official Work module."
                    )
                },
                status=400
            )

        # --------------------------------------------------
        # ATTACHMENT VALIDATION (medical / sick leave only)
        # --------------------------------------------------
        attachment_error = validate_attachment(upload, leave_type)
        if attachment_error:
            return JsonResponse({"error": attachment_error}, status=400)

        # --------------------------------------------------
        # DATE PARSING
        # --------------------------------------------------
        try:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            return JsonResponse(
                {"error": "Invalid date format. Use YYYY-MM-DD"},
                status=400
            )

        if start_date > end_date:
            return JsonResponse(
                {"error": "start_date cannot be greater than end_date"},
                status=400
            )

        # --------------------------------------------------
        # GENDER RESTRICTION CHECK
        # --------------------------------------------------
        required_gender = GENDER_RESTRICTED_LEAVE_TYPES.get(leave_type.lower())
        if required_gender:
            employee = Employees.objects.filter(erp_id=erp_id).first()
            if not employee or (employee.gender or "").upper() != required_gender:
                return JsonResponse(
                    {"error": f"'{leave_type}' is not applicable for this employee"},
                    status=400
                )

        # --------------------------------------------------
        # MINIMUM SERVICE LENGTH CHECK
        # --------------------------------------------------
        required_service_years = MIN_SERVICE_YEARS_LEAVE_TYPES.get(leave_type.lower())
        if required_service_years:
            years_of_service = get_employee_years_of_service(erp_id)
            if years_of_service is None:
                return JsonResponse(
                    {"error": f"Unable to verify service tenure required for '{leave_type}'"},
                    status=400
                )
            if years_of_service < required_service_years:
                return JsonResponse(
                    {
                        "error": (
                            f"'{leave_type}' requires at least {required_service_years} years of service "
                            f"(current tenure: {years_of_service:.1f} years)"
                        )
                    },
                    status=400
                )

        requested_days = (end_date - start_date).days + 1

        # --------------------------------------------------
        # WEEKEND / PUBLIC HOLIDAY CHECK
        # Weekends and public holidays are allowed when "sandwiched" inside a
        # leave request (i.e. at least one working day is actually being taken
        # off). This lets a leave span an intervening public holiday — e.g.
        # 23 Jul -> 21 Aug across the 14th Aug holiday.
        # Only a request made up *entirely* of weekend / public holiday day(s)
        # is rejected, since that isn't a real leave.
        # --------------------------------------------------
        holiday_dates = set(
            Holiday.objects.filter(
                date__gte=start_date, date__lte=end_date
            ).values_list("date", flat=True)
        )

        has_working_day = False
        day_cursor = start_date
        while day_cursor <= end_date:
            is_weekend = day_cursor.weekday() in (5, 6)  # Saturday/Sunday
            is_holiday = day_cursor in holiday_dates
            if not is_weekend and not is_holiday:
                has_working_day = True
                break
            day_cursor += timedelta(days=1)

        if not has_working_day:
            return JsonResponse(
                {"error": "Leave cannot be applied only for weekend or public holiday day(s)"},
                status=400
            )

        # --------------------------------------------------
        # DUPLICATE / CONFLICTING LEAVE CHECK (SAME DATES)
        # --------------------------------------------------
        overlapping_leaves = LeaveModel.objects.filter(
            erp_id=erp_id,
            start_date__lte=end_date,
            end_date__gte=start_date,
        ).exclude(
            Q(status__iexact="rejected") | Q(status__iexact="cancelled")
        )

        for existing in overlapping_leaves:
            if existing.leave_type == leave_type:
                return JsonResponse(
                    {"error": f"A '{leave_type}' request already exists for the selected date(s)"},
                    status=400
                )
            return JsonResponse(
                {
                    "error": (
                        f"Cannot apply for '{leave_type}' — a different leave type "
                        f"('{existing.leave_type}') already exists for the selected date(s)"
                    )
                },
                status=400
            )

        # --------------------------------------------------
        # OFFICIAL WORK CONFLICT CHECK (SAME DATES)
        # --------------------------------------------------
        overlapping_official_work = OfficialWorkModel.objects.filter(
            erp_id=erp_id,
            start_date__lte=end_date,
            end_date__gte=start_date,
        ).exclude(
            Q(status__iexact="rejected") | Q(status__iexact="cancelled")
        )

        if overlapping_official_work.exists():
            return JsonResponse(
                {"error": "Cannot apply leave — Official Work already exists for the selected date(s)"},
                status=400
            )

        # --------------------------------------------------
        # FINANCIAL YEAR CALCULATION
        # FY = 1 July (year) → 30 June (next year)
        # --------------------------------------------------
        fy_start = date(start_date.year, 7, 1)
        fy_end = date(start_date.year + 1, 6, 30)

        # Ensure leave does not cross financial year
        if end_date > fy_end:
            return JsonResponse(
                {
                    "error": "Leave request cannot exceed financial year",
                    "financial_year_start": fy_start,
                    "financial_year_end": fy_end,
                },
                status=400
            )

        # --------------------------------------------------
        # FETCH TOTAL ALLOWED LEAVES
        # --------------------------------------------------
        leave_limit = LeaveTypeCountModel.objects.filter(
            leave_type=leave_type
        ).first()

        if not leave_limit:
            return JsonResponse(
                {"error": f"No leave balance defined for {leave_type}"},
                status=400
            )

        total_allowed = leave_limit.total_leaves

        # --------------------------------------------------
        # CALCULATE USED LEAVES (WITHIN FINANCIAL YEAR)
        # --------------------------------------------------
        used_leaves = LeaveModel.objects.filter(
            erp_id=erp_id,
            leave_type=leave_type,
            status__in=["approved", "pending"],
            start_date__lte=fy_end,
            end_date__gte=fy_start,
        )

        used_days = 0
        for leave in used_leaves:
            if leave.start_date and leave.end_date:
                actual_start = max(leave.start_date, fy_start)
                actual_end = min(leave.end_date, fy_end)
                used_days += (actual_end - actual_start).days + 1

        # --------------------------------------------------
        # CASUAL LEAVE RULE (RR = +10 DAYS)
        # --------------------------------------------------
        if leave_type.lower() == "casual leave":
            has_rr_leave = LeaveModel.objects.filter(
                erp_id=erp_id,
                leave_type="Rest & Recreational Leave",
                status__in=["approved", "pending"],
                start_date__lte=fy_end,
                end_date__gte=fy_start,
            ).exists()

            if has_rr_leave:
                used_days += 10

        # --------------------------------------------------
        # FINAL BALANCE CHECK (FY-BASED)
        # --------------------------------------------------
        remaining_leaves = total_allowed - used_days

        if remaining_leaves <= 0 and leave_type.lower() != "short leave":
            return JsonResponse(
                {
                    "error": "No leaves available in account for current financial year",
                    "financial_year": f"{fy_start} to {fy_end}",
                    "used_leaves": used_days,
                    "total_allowed": total_allowed,
                },
                status=400
            )

        if requested_days > remaining_leaves and leave_type.lower() != "short leave":
            return JsonResponse(
                {
                    "error": "Insufficient leave balance for current financial year",
                    "requested_days": requested_days,
                    "remaining_leaves": remaining_leaves,
                },
                status=400
            )

        # --------------------------------------------------
        # CREATE LEAVE REQUEST, Entry made by is erp id of logged in user
        # --------------------------------------------------
        # Every application starts as pending and goes to the section head for
        # approval — the same rule for grade 9 and above as for everyone else.
        # The status is fixed here rather than taken from the request, so it
        # cannot be set by whatever the client posts.
        leave = LeaveModel.objects.create(
            erp_id=erp_id,
            employee_id=employee_id,
            head_erpid=data.get("head", 0),
            entry_made_by=data.get("entry_made_by", 0),
            leave_type=leave_type,
            reason=data.get("reason", ""),
            total_days=requested_days,
            status="pending",
            approved_by=data.get("approved_by", ""),
            start_date=start_date,
            end_date=end_date,
        )

        if upload is not None:
            # Stored under a generated name; the uploaded one is display only.
            leave.attachment_original_name = upload.name
            leave.attachment.save(
                build_attachment_name(upload.name),
                ContentFile(upload.read()),
                save=True,
            )

        # Let the section head know something is waiting on them.
        notify_leave_submitted(leave)

        return JsonResponse(
            {
                "message": "Leave request created successfully",
                "leave_id": leave.pk,
                "status": leave.status,
                "financial_year": f"{fy_start} to {fy_end}",
                "remaining_leaves": remaining_leaves - requested_days,
                **attachment_payload(leave, request),
            },
            status=201
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
@require_POST
def handle_leave_request(request):
    data = json.loads(request.body.decode('utf-8'))
    leave_id = data.get("recordid")
    action = data.get("action")

    if action == "approve":
        LeaveModel.objects.filter(pk=leave_id).update(status="approved")
    elif action == "reject":
        LeaveModel.objects.filter(pk=leave_id).update(status="rejected")

    # Tell the applicant. Read back after the update so the notification
    # reflects what was actually stored, and so a bad id simply produces no
    # notification instead of an error.
    if action in ("approve", "reject"):
        leave = LeaveModel.objects.filter(pk=leave_id).first()
        if leave is not None:
            notify_leave_decision(
                leave, action, actor_erp_id=data.get("actor_erp_id")
            )

    return JsonResponse({"message": "Leave request updated successfully"})

    
