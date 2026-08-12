from django.shortcuts import render
from django.http import JsonResponse
from .models import OfficialWorkModel
from django.views.decorators.http import require_GET,require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
import json
from sqlalchemy import text
from db import SessionLocal
from datetime import datetime, date, timedelta
from leaves.models import LeaveModel
from holidays.models import Holiday
from notifications.service import (
    notify_official_work_decision,
    notify_official_work_submitted,
)
# Create your views here.

@require_GET
def get_leave_requests(request,erpid):
    leaves = OfficialWorkModel.objects.all()
    data=[]
    sessions= SessionLocal()
    query = text("""
        SELECT
            l.id,
            e.name AS employee_name,
            l.employee_id,
            l.erp_id,
            l.leave_type,
            l.head_erpid,
            h.name AS headname,
            l.start_date,
            l.end_date,
            l.reason,
            l.status,
            l.created_at
        FROM official_work_leaves l
        LEFT JOIN employees e ON l.erp_id = e.erp_id
        LEFT JOIN employees h ON l.head_erpid = h.erp_id
        WHERE e.flag = 1
          AND e.section_id = (SELECT section_id FROM employees WHERE erp_id = :epid)
        ORDER BY l.created_at DESC
    """)
    result = sessions.execute(query, {"epid": erpid}).fetchall()
    
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
            "head_erpid": '-' if row[5] == 0 else row[5],
        })
    sessions.close()
    return JsonResponse({"leaves": data})


@csrf_exempt
@require_POST
def get_official_work_balance(request):
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

    # Official Work has no configured entitlement/limit — this is a running
    # count of days recorded for the type, not a balance.
    used_leaves = OfficialWorkModel.objects.filter(
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

    return JsonResponse(
        {
            "leave_type": leave_type,
            "used_days": used_days,
            "financial_year": f"{fy_start.strftime('%d-%b-%Y')} to {fy_end.strftime('%d-%b-%Y')}",
        },
        status=200
    )


@csrf_exempt
@require_POST
def create_official_work_request(request):
    try:
        data = json.loads(request.body.decode('utf-8'))

        erp_id = data.get("erp_id")
        employee_id = data.get("employee_id")
        start_date = data.get("start_date")
        end_date = data.get("end_date")

        # --------------------------------------------------
        # REQUIRED FIELDS CHECK
        # --------------------------------------------------
        if not all([erp_id, employee_id, start_date, end_date]):
            return JsonResponse(
                {"error": "erp_id, employee_id, start_date and end_date are required"},
                status=400
            )

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
        # WEEKEND / PUBLIC HOLIDAY CHECK
        # Weekends are allowed when "sandwiched" inside a request
        # (i.e. at least one working day is actually being taken off).
        # A request made up of only weekend day(s) is rejected.
        # --------------------------------------------------
        holiday_dates = set(
            Holiday.objects.filter(
                date__gte=start_date, date__lte=end_date
            ).values_list("date", flat=True)
        )

        has_working_day = False
        day_cursor = start_date
        while day_cursor <= end_date:
            if day_cursor in holiday_dates:
                return JsonResponse(
                    {"error": f"Official Work cannot be applied on a public holiday ({day_cursor})"},
                    status=400
                )
            if day_cursor.weekday() not in (5, 6):  # not Saturday/Sunday
                has_working_day = True
            day_cursor += timedelta(days=1)

        if not has_working_day:
            return JsonResponse(
                {"error": "Official Work cannot be applied only for weekend day(s)"},
                status=400
            )

        # --------------------------------------------------
        # DUPLICATE / CONFLICTING OFFICIAL WORK CHECK (SAME DATES)
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
                {"error": "An Official Work request already exists for the selected date(s)"},
                status=400
            )

        # --------------------------------------------------
        # LEAVE CONFLICT CHECK (SAME DATES)
        # --------------------------------------------------
        overlapping_leaves = LeaveModel.objects.filter(
            erp_id=erp_id,
            start_date__lte=end_date,
            end_date__gte=start_date,
        ).exclude(
            Q(status__iexact="rejected") | Q(status__iexact="cancelled")
        )

        if overlapping_leaves.exists():
            return JsonResponse(
                {"error": "Cannot apply Official Work — a leave request already exists for the selected date(s)"},
                status=400
            )

        official_work = OfficialWorkModel.objects.create(
            erp_id=erp_id,
            employee_id=employee_id,
            leave_type=data.get("leave_type", ""),
            reason=data.get("reason", ""),
            status=data.get("status", ""),
            head_erpid=data.get("head_erpid", ""),
            approved_by=data.get("approved_by", ""),
            start_date=start_date,
            end_date=end_date,
        )

        # Let the section head know something is waiting on them.
        notify_official_work_submitted(official_work)

        return JsonResponse(
            {"message": "Official Work request created successfully", "id": official_work.pk},
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
        OfficialWorkModel.objects.filter(pk=leave_id).update(status="approved")
    elif action == "reject":
        OfficialWorkModel.objects.filter(pk=leave_id).update(status="rejected")

    # Tell the applicant. Read back after the update so a bad id simply
    # produces no notification rather than an error.
    if action in ("approve", "reject"):
        record = OfficialWorkModel.objects.filter(pk=leave_id).first()
        if record is not None:
            notify_official_work_decision(
                record, action, actor_erp_id=data.get("actor_erp_id")
            )

    return JsonResponse({"message": "Leave request updated successfully"})
