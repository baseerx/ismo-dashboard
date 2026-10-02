from django.shortcuts import render
from django.http import JsonResponse, FileResponse
from django.conf import settings
from django.core.files.base import ContentFile
from .models import LeaveModel, LeaveTypeCountModel, LeaveApprovalStage
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

# Phase 1 rule engine (leave_rules.py) and the multi-stage approval
# workflow (approval_workflow.py) — both standalone modules, imported
# here so create_leave_request / get_leave_requests can use them.
from .leave_rules import (
    REMOVED_LEAVE_TYPES,
    check_removed_leave_type,
    enforce_max_days_per_request,
    check_hajj_occurrence,
    paternity_alert,
    resolve_maternity_leave_type,
    MATERNITY_SEQUENCE,
    check_rr_prerequisite,
    split_medical_leave_lwp,
    resolve_ex_pakistan_shortfall,
    validate_attachment_universal,
)
from .approval_workflow import initialize_approval_chain, serialize_current_stage
# NEW: employee category (Jamshoro / Planning & Lahore / CPPA-MO) by location.
from .location_groups import category_for_location

# Create your views here.

GENDER_RESTRICTED_LEAVE_TYPES = {
    "maternity leave first": "F",
    "maternity leave second": "F",
    "maternity leave third": "F",
    "iddat leave": "F",
    "paternity leave": "M",
}

MIN_SERVICE_YEARS_LEAVE_TYPES = {
    "hajj leave": 3,
}


def current_financial_year(today=None):
    
    today = today or date.today()

    if today.month >= 7:
        return date(today.year, 7, 1), date(today.year + 1, 6, 30)
    return date(today.year - 1, 7, 1), date(today.year, 6, 30)


def get_employee_years_of_service(erp_id):
    
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

    fy_start, fy_end = current_financial_year()

    base_query = """
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
            l.created_at,
            d.title AS designation,
            loc.name AS location_name,
            e.date_of_joining,
            e.date_of_birth
        FROM leaves l
        LEFT JOIN employees e
            ON l.erp_id = e.erp_id
        LEFT JOIN employees h
            ON l.head_erpid = h.erp_id
        LEFT JOIN designations d ON e.designation_id = d.id
        LEFT JOIN locations loc ON e.location_id = loc.id
        WHERE e.flag = 1
          AND l.start_date IS NOT NULL
          AND l.end_date IS NOT NULL
          AND l.start_date <= :fy_end
          AND l.end_date >= :fy_start
          {extra_clause}
        ORDER BY l.created_at DESC
    """

    own_section_query = text(base_query.format(
        extra_clause="AND e.section_id = (SELECT section_id FROM employees WHERE erp_id = :epid)"
    ))
    own_section_rows = sessions.execute(
        own_section_query,
        {"epid": erpid, "fy_start": fy_start, "fy_end": fy_end},
    ).fetchall()

    seen_ids = {row[0] for row in own_section_rows}
    result = list(own_section_rows)

    pending_leave_ids = list(
        LeaveApprovalStage.objects.filter(
            assigned_erp_id=erpid, status="pending"
        ).values_list("leave_id", flat=True)
    )
    extra_ids = [pk for pk in pending_leave_ids if pk not in seen_ids]

    if extra_ids:
        cross_dept_query = text(base_query.format(
            extra_clause="AND l.id IN :leave_ids"
        )).bindparams(bindparam("leave_ids", expanding=True))
        cross_dept_rows = sessions.execute(
            cross_dept_query,
            {"leave_ids": extra_ids, "fy_start": fy_start, "fy_end": fy_end},
        ).fetchall()
        result.extend(cross_dept_rows)
        seen_ids.update(row[0] for row in cross_dept_rows)

    result.sort(key=lambda row: row[11], reverse=True)  # created_at desc

    
    leave_ids = [row[0] for row in result]
    leave_objs = list(LeaveModel.objects.filter(pk__in=leave_ids)) if leave_ids else []
    attachments = {
        leave.pk: attachment_payload(leave, request) for leave in leave_objs
    }
    stage_info = {
        leave.pk: serialize_current_stage(leave) for leave in leave_objs
    }
    no_attachment = {
        "has_attachment": False,
        "attachment_name": None,
        "attachment_url": None,
    }
    no_stage = {
        "current_stage_label": None,
        "current_stage_role": None,
        "current_stage_erp_id": None,
    }
    training_days = {}
    erp_set = {row[3] for row in result}
    if erp_set:
        for ow in OfficialWorkModel.objects.filter(
            erp_id__in=erp_set,
            leave_type__iexact="Training",
            start_date__lte=fy_end,
            end_date__gte=fy_start,
        ).exclude(Q(status__iexact="rejected") | Q(status__iexact="cancelled")):
            if ow.start_date and ow.end_date:
                first = max(ow.start_date, fy_start)
                last = min(ow.end_date, fy_end)
                if first <= last:
                    training_days[ow.erp_id] = (
                        training_days.get(ow.erp_id, 0) + (last - first).days + 1
                    )

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
            "designation": row[12],
            "location": row[13],
            "category": category_for_location(row[13]),
            "joining_date": row[14].strftime('%d-%m-%Y') if row[14] else None,
            "date_of_birth": row[15].strftime('%d-%m-%Y') if row[15] else None,
            "official_training_days": training_days.get(row[3], 0),
            **attachments.get(row[0], no_attachment),
            **(stage_info.get(row[0]) or no_stage),
        })
    sessions.close()
    return JsonResponse(
        {
            "leaves": data,
            
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
        today = date.today()

        if today.month >= 7:
            fy_start = date(today.year, 7, 1)
            fy_end = date(today.year + 1, 6, 30)
        else:
            fy_start = date(today.year - 1, 7, 1)
            fy_end = date(today.year, 6, 30)

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
OFFICIAL_WORK_LEAVE_TYPE = "Official Work"


def get_official_work_records(
    session,
    section_id,
    start_date,
    end_date,
    include_pending,
    erp_id=None,
):
    
    status_clause = (
        "IN ('approved', 'pending')" if include_pending else "= 'approved'"
    )
    erp_clause = "AND r.erp_id = :erp_id" if erp_id else ""

 
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
            
            "_days": days,
        })

    return records


def official_work_day_sets(records):
   
    days_by_erp = {}
    for record in records:
        days_by_erp.setdefault(record["erp_id"], set()).update(record["_days"])
    return days_by_erp


def fetch_official_work_module_rows(
    session, erp_id, range_start, range_end, include_pending=False
):
    
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



def build_attachment_name(original_name):
    
    extension = os.path.splitext(original_name or "")[1].lower()
    return f"{uuid.uuid4().hex}{extension}"


def attachment_payload(leave, request=None):
   
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
    
    safe_name = display_name.replace('"', "")
    response["Content-Disposition"] = f'inline; filename="{safe_name}"'
    return response


def strip_internal_fields(records):
    
    return [
        {key: value for key, value in record.items() if not key.startswith("_")}
        for record in records
    ]


def summarize_official_work(records):
    
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



def parse_report_range(start_date, end_date):
    
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None, None, "start_date and end_date must be YYYY-MM-DD"

    if start > end:
        return None, None, "start_date must be on or before end_date"

    return start, end, None


def clipped_days(row_start, row_end, range_start, range_end):
   
    if row_start is None or row_end is None or row_end < row_start:
        return []

    first = max(row_start, range_start)
    last = min(row_end, range_end)
    if first > last:
        return []

    return [first + timedelta(days=offset)
            for offset in range((last - first).days + 1)]


def fetch_section_employees(session, section_id, erp_id=None):
    
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
        quality["overlapping_days_merged"] += len(days) - (len(bucket) - before)

    return days_by_erp, quality


def fetch_leave_allocation(session, leave_type):
    
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
    leave_type = data.get("leave_type")   
    start_date = data.get("start_date")
    end_date = data.get("end_date")

    
    if not all([section, leave_type, start_date, end_date]):
        return JsonResponse(
            {"error": "section, leave_type, start_date, and end_date are required"},
            status=400
        )

    start_date, end_date, range_error = parse_report_range(start_date, end_date)
    if range_error:
        return JsonResponse({"error": range_error}, status=400)

    include_pending = False

    sessions = SessionLocal()

    try:
        employees, duplicate_employees = fetch_section_employees(
            sessions, section, erpid or None
        )
        erp_ids = [emp.erp_id for emp in employees]

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
   
    if not all([section, start_date, end_date]):
        return JsonResponse(
            {"error": "section, start_date, and end_date are required"},
            status=400
        )

    start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

    sessions = SessionLocal()

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

    employee_gender = (emp[4] or "").upper()
    years_of_service = get_employee_years_of_service(emp[1])

    has_rr_leave = LeaveModel.objects.filter(
        erp_id=emp[1],
        leave_type="Rest & Recreational Leave",
        start_date__lte=end_date,
        end_date__gte=start_date,
        status__iexact="approved",
    ).exists()

    all_types = sessions.execute(text("""
        SELECT leave_type, total_leaves
        FROM leave_type_counts
        ORDER BY leave_type
    """)).fetchall()

    filtered_leaves_query = text("""
        SELECT start_date, end_date
        FROM leaves
        WHERE erp_id = :erp_id
          AND LOWER(status) = 'approved'
          AND leave_type = :leave_type
          AND start_date <= :end_date
          AND end_date >= :start_date
    """)

    official_work_module_days = set()
    if any(is_official_work(row[0]) for row in all_types):
        for ow_row in fetch_official_work_module_rows(
            sessions, emp[1], start_date, end_date, include_pending=False
        ):
            official_work_module_days.update(
                clipped_days(ow_row[1], ow_row[2], start_date, end_date)
            )

    result = []

    for type_row in all_types:
        leave_type = type_row[0]
        total_leaves = type_row[1]
        lt_lower = (leave_type or "").lower()

        if lt_lower in REMOVED_LEAVE_TYPES:
            continue

        required_gender = GENDER_RESTRICTED_LEAVE_TYPES.get(lt_lower)
        if required_gender and employee_gender != required_gender:
            continue

        required_service_years = MIN_SERVICE_YEARS_LEAVE_TYPES.get(lt_lower)
        if required_service_years and (
            years_of_service is None or years_of_service < required_service_years
        ):
            continue

        leaves = sessions.execute(
            filtered_leaves_query,
            {
                "erp_id": emp[1],
                "leave_type": leave_type,
                "start_date": start_date,
                "end_date": end_date,
            },
        ).fetchall()

        day_set = set()
        for leave in leaves:
            day_set.update(clipped_days(leave[0], leave[1], start_date, end_date))

        if is_official_work(leave_type):
            day_set |= official_work_module_days

        leave_count = len(day_set)

        if lt_lower == "casual leave" and has_rr_leave:
            leave_count += 10

        remaining_leaves = (
            total_leaves - leave_count if total_leaves is not None else None
        )

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
    
    if not all([section, leave_type, start_date, end_date]):
        return JsonResponse(
            {"error": "section, leave_type, start_date, and end_date are required"},
            status=400
        )
    start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

    sessions = SessionLocal()

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
        sessions.close()
        return JsonResponse({"error": "Employee not found"}, status=404)

    result = []

    for emp in employees:
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

    include_pending = False

    session = SessionLocal()

    try:
        employees, duplicate_employees = fetch_section_employees(
            session, section_id
        )
        erp_ids = [emp.erp_id for emp in employees]

        days_by_erp, quality = fetch_leave_days(
            session, erp_ids, leave_type, include_pending, start_date, end_date
        )

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

        
        if not all([erp_id, employee_id, leave_type, start_date, end_date]):
            return JsonResponse(
                {"error": "erp_id, employee_id, leave_type, start_date and end_date are required"},
                status=400
            )

        removed_error = check_removed_leave_type(leave_type)
        if removed_error:
            return JsonResponse({"error": removed_error}, status=400)

       
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

        attachment_error = validate_attachment_universal(upload)
        if attachment_error:
            return JsonResponse({"error": attachment_error}, status=400)

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

        requested_days = (end_date - start_date).days + 1

        lt_lower = leave_type.strip().lower()
        warnings = []

        
        if lt_lower == "leave ex-pakistan" and not (data.get("reason") or "").strip():
            return JsonResponse(
                {"error": "Please mention the country/destination and purpose in the reason for Leave Ex-Pakistan."},
                status=400,
            )

        cap_error = enforce_max_days_per_request(leave_type, requested_days)
        if cap_error:
            return JsonResponse({"error": cap_error}, status=400)

        if lt_lower == "hajj leave":
            hajj_error = check_hajj_occurrence(erp_id)
            if hajj_error:
                return JsonResponse({"error": hajj_error}, status=400)

        if lt_lower == "paternity leave":
            alert = paternity_alert(erp_id)
            if alert:
                warnings.append(alert)

        if leave_type in MATERNITY_SEQUENCE:
            resolved_type, maternity_error = resolve_maternity_leave_type(erp_id)
            if maternity_error:
                return JsonResponse({"error": maternity_error}, status=400)
            if resolved_type != leave_type:
                leave_type = resolved_type
                lt_lower = leave_type.lower()

        required_gender = GENDER_RESTRICTED_LEAVE_TYPES.get(lt_lower)
        if required_gender:
            employee = Employees.objects.filter(erp_id=erp_id).first()
            if not employee or (employee.gender or "").upper() != required_gender:
                return JsonResponse(
                    {"error": f"'{leave_type}' is not applicable for this employee"},
                    status=400
                )

        required_service_years = MIN_SERVICE_YEARS_LEAVE_TYPES.get(lt_lower)
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

        fy_start = date(start_date.year, 7, 1)
        fy_end = date(start_date.year + 1, 6, 30)

        if end_date > fy_end:
            return JsonResponse(
                {
                    "error": "Leave request cannot exceed financial year",
                    "financial_year_start": fy_start,
                    "financial_year_end": fy_end,
                },
                status=400
            )

        if lt_lower == "rest & recreational leave":
            rr_error = check_rr_prerequisite(erp_id, fy_start, fy_end)
            if rr_error:
                return JsonResponse({"error": rr_error}, status=400)

       
        leave_limit = LeaveTypeCountModel.objects.filter(
            leave_type=leave_type
        ).first()

        if not leave_limit:
            return JsonResponse(
                {"error": f"No leave balance defined for {leave_type}"},
                status=400
            )

        total_allowed = leave_limit.total_leaves

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

        if lt_lower == "casual leave":
            has_rr_leave = LeaveModel.objects.filter(
                erp_id=erp_id,
                leave_type="Rest & Recreational Leave",
                status__in=["approved", "pending"],
                start_date__lte=fy_end,
                end_date__gte=fy_start,
            ).exists()

            if has_rr_leave:
                used_days += 10

        
        lwp_days = 0
        if lt_lower == "medical leave":
            _, lwp_days = split_medical_leave_lwp(erp_id, requested_days, fy_start, fy_end)
        elif lt_lower == "leave ex-pakistan":
            _, lwp_days = resolve_ex_pakistan_shortfall(erp_id, requested_days, fy_start, fy_end)

        
        remaining_leaves = total_allowed - used_days

        skip_balance_check = lt_lower in ("short leave", "medical leave", "leave ex-pakistan")

        if remaining_leaves <= 0 and not skip_balance_check:
            return JsonResponse(
                {
                    "error": "No leaves available in account for current financial year",
                    "financial_year": f"{fy_start} to {fy_end}",
                    "used_leaves": used_days,
                    "total_allowed": total_allowed,
                },
                status=400
            )

        if requested_days > remaining_leaves and not skip_balance_check:
            return JsonResponse(
                {
                    "error": "Insufficient leave balance for current financial year",
                    "requested_days": requested_days,
                    "remaining_leaves": remaining_leaves,
                },
                status=400
            )

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
            is_lwp_overflow=lwp_days > 0,
            lwp_days=lwp_days,
        )

        if upload is not None:
            leave.attachment_original_name = upload.name
            leave.attachment.save(
                build_attachment_name(upload.name),
                ContentFile(upload.read()),
                save=True,
            )

       
        initialize_approval_chain(leave)

        return JsonResponse(
            {
                "message": "Leave request created successfully",
                "leave_id": leave.pk,
                "status": leave.status,
                "financial_year": f"{fy_start} to {fy_end}",
                "remaining_leaves": remaining_leaves - requested_days,
                "warnings": warnings,
                "lwp_days": lwp_days,
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

    if action in ("approve", "reject"):
        leave = LeaveModel.objects.filter(pk=leave_id).first()
        if leave is not None:
            notify_leave_decision(
                leave, action, actor_erp_id=data.get("actor_erp_id")
            )

    return JsonResponse({"message": "Leave request updated successfully"})