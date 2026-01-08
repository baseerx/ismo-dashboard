from django.shortcuts import render
from django.http import JsonResponse
from .models import LeaveModel
from django.views.decorators.http import require_GET,require_POST
from django.views.decorators.csrf import csrf_exempt
import json
from sqlalchemy import text
from db import SessionLocal
from datetime import datetime
# Create your views here.

@require_GET
def get_leave_requests(request,erpid):
    leaves = LeaveModel.objects.all()
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
            "head_erpid": '-' if row[5]==0 else row[5],
            "head_name": row[6]
        })
    sessions.close()
    return JsonResponse({"leaves": data},status=200)


@csrf_exempt
@require_POST
def get_leaves_count(request):
    data = json.loads(request.body.decode('utf-8'))
    erpid = data.get("erp_id", 0)
    section = data.get("section", None)  # Expecting section from frontend

    sessions = SessionLocal()

    if erpid == 0 and section:
        # Case 1: erp_id is zero → get all employees in given section
        query = text("""
            SELECT
                e.section_id,
                e.erp_id,
                e.name AS employee_name,
                e.id AS employee_id,
                s.name AS section_name
            FROM employees e
            LEFT JOIN sections s ON e.section_id = s.id
            WHERE e.flag = 1
              AND e.section_id = :section
        """)
        employees = sessions.execute(query, {"section": section}).fetchall()

    else:
        # Case 2: erp_id provided → get only that employee inside the section
        query = text("""
            SELECT
                e.section_id,
                e.erp_id,
                e.name AS employee_name,
                e.id AS employee_id,
                s.name AS section_name
            FROM employees e
            LEFT JOIN sections s ON e.section_id = s.id
            WHERE e.flag = 1
              AND e.section_id = :section
              AND e.erp_id = :epid
        """)
        employees = sessions.execute(
            query, {"section": section, "epid": erpid}).fetchall()

    result = []
    for emp in employees:
        # --- leaves table ---
        leaves_query = text("""
            SELECT start_date, end_date
            FROM leaves
            WHERE erp_id = :empid AND status='approved'
        """)
        leaves = sessions.execute(leaves_query, {"empid": emp[1]}).fetchall()

        leave_count = 0
        for leave in leaves:
            if leave[0] and leave[1]:
                leave_count += (leave[1] - leave[0]).days + 1

        # --- official_work_leaves table ---
        official_query = text("""
            SELECT start_date, end_date
            FROM official_work_leaves
            WHERE erp_id = :empid
              AND status = 'approved'
        """)
        official_leaves = sessions.execute(
            official_query, {"empid": emp[1]}).fetchall()

        for leave in official_leaves:
            if leave[0] and leave[1]:
                leave_count += (leave[1] - leave[0]).days + 1

        # --- Final append ---
        result.append({
            "id": emp[3],
            "employee_id": emp[3],
            "employee_name": emp[2],
            "section": emp[4],  # section name from join
            "erp_id": emp[1],
            "leave_count": leave_count
        })

    sessions.close()
    return JsonResponse({"attendance": result}, status=200)


@csrf_exempt
@require_POST
def individual_report(request):
    data = json.loads(request.body.decode("utf-8"))

    erpid = data.get("erp_id", 0)
    section = data.get("section")
    leave_type = data.get("leave_type")   # REQUIRED
    start_date = data.get("start_date")
    end_date = data.get("end_date")

    # Convert dates to Python date objects
    start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

    sessions = SessionLocal()

    # ----------------------------------------------------
    # FETCH EMPLOYEES
    # ----------------------------------------------------
    if erpid == 0:
        query = text("""
            SELECT
                e.id AS employee_id,
                e.erp_id,
                e.name AS employee_name,
                s.name AS section_name
            FROM employees e
            LEFT JOIN sections s ON e.section_id = s.id
            WHERE e.flag = 1
              AND e.section_id = :section
        """)
        employees = sessions.execute(query, {"section": section}).fetchall()
    else:
        query = text("""
            SELECT
                e.id AS employee_id,
                e.erp_id,
                e.name AS employee_name,
                s.name AS section_name
            FROM employees e
            LEFT JOIN sections s ON e.section_id = s.id
            WHERE e.flag = 1
              AND e.section_id = :section
              AND e.erp_id = :erp_id
        """)
        employees = sessions.execute(
            query, {"section": section, "erp_id": erpid}
        ).fetchall()

    result = []

    # ----------------------------------------------------
    # LOOP EMPLOYEES
    # ----------------------------------------------------
    for emp in employees:
        leave_count = 0

        # ------------------------------------------------
        # FILTERED LEAVES (by type + date range)
        # ------------------------------------------------
        leaves_query = text("""
            SELECT start_date, end_date
            FROM leaves
            WHERE erp_id = :erp_id
              AND status = 'approved'
              AND leave_type = :leave_type
              AND start_date <= :end_date
              AND end_date >= :start_date
        """)

        leaves = sessions.execute(
            leaves_query,
            {
                "erp_id": emp.erp_id,
                "leave_type": leave_type,
                "start_date": start_date,
                "end_date": end_date,
            },
        ).fetchall()

        for leave in leaves:
            actual_start = max(leave.start_date, start_date)
            actual_end = min(leave.end_date, end_date)
            leave_count += (actual_end - actual_start).days + 1

        # ------------------------------------------------
        # OFFICIAL WORK LEAVES (OPTIONAL – remove if not needed)
        # ------------------------------------------------
        official_query = text("""
            SELECT start_date, end_date
            FROM official_work_leaves
            WHERE erp_id = :erp_id
              AND status = 'approved'
              AND start_date <= :end_date
              AND end_date >= :start_date
        """)

        official_leaves = sessions.execute(
            official_query,
            {
                "erp_id": emp.erp_id,
                "start_date": start_date,
                "end_date": end_date,
            },
        ).fetchall()

        for leave in official_leaves:
            actual_start = max(leave.start_date, start_date)
            actual_end = min(leave.end_date, end_date)
            leave_count += (actual_end - actual_start).days + 1

        # ------------------------------------------------
        # RESPONSE
        # ------------------------------------------------
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

    sessions.close()
    return JsonResponse({"attendance": result}, status=200)


@csrf_exempt
@require_POST
def section_leave_report(request):
    data = json.loads(request.body.decode("utf-8"))

    section_id = data.get("section")          # REQUIRED
    leave_type = data.get("leave_type")       # REQUIRED
    start_date = data.get("start_date")       # REQUIRED
    end_date = data.get("end_date")           # REQUIRED

    if not all([section_id, leave_type, start_date, end_date]):
        return JsonResponse(
            {"error": "section, leave_type, start_date, end_date are required"},
            status=400
        )

    start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

    session = SessionLocal()

    # ----------------------------------------------------
    # FETCH ALL ACTIVE EMPLOYEES OF SECTION
    # ----------------------------------------------------
    employees_query = text("""
        SELECT
            e.id AS employee_id,
            e.erp_id,
            e.name AS employee_name,
            s.name AS section_name
        FROM employees e
        JOIN sections s ON e.section_id = s.id
        WHERE e.flag = 1
          AND e.section_id = :section_id
    """)

    employees = session.execute(
        employees_query,
        {"section_id": section_id}
    ).fetchall()

    result = []

    # ----------------------------------------------------
    # LOOP THROUGH EMPLOYEES
    # ----------------------------------------------------
    for emp in employees:
        leave_count = 0

        # -----------------------------------------------
        # FETCH APPROVED LEAVES (TYPE + DATE RANGE)
        # -----------------------------------------------
        leaves_query = text("""
            SELECT start_date, end_date
            FROM leaves
            WHERE erp_id = :erp_id
              AND status = 'approved'
              AND leave_type = :leave_type
              AND start_date <= :end_date
              AND end_date >= :start_date
        """)

        leaves = session.execute(
            leaves_query,
            {
                "erp_id": emp.erp_id,
                "leave_type": leave_type,
                "start_date": start_date,
                "end_date": end_date,
            }
        ).fetchall()

        # -----------------------------------------------
        # CALCULATE OVERLAPPING DAYS
        # -----------------------------------------------
        for leave in leaves:
            actual_start = max(leave.start_date, start_date)
            actual_end = min(leave.end_date, end_date)
            leave_count += (actual_end - actual_start).days + 1

        # -----------------------------------------------
        # APPEND RESULT
        # -----------------------------------------------
        result.append({
            "employee_id": emp.employee_id,
            "erp_id": emp.erp_id,
            "employee_name": emp.employee_name,
            "section": emp.section_name,
            "leave_type": leave_type,
            "leave_count": leave_count,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
        })

    session.close()

    return JsonResponse({"attendance": result}, status=200)


@csrf_exempt
@require_POST
def create_leave_request(request):
    data = json.loads(request.body.decode('utf-8'))
   
    leave = LeaveModel.objects.create(
        erp_id=data.get("erp_id", 0),
        employee_id=data.get("employee_id", 0),
        head_erpid=data.get("head", 0),
        leave_type=data.get("leave_type", ""),
        reason=data.get("reason", ""),
        status=data.get("status", ""),
        approved_by=data.get("approved_by", ""),
        start_date=data.get("start_date"),
        end_date=data.get("end_date"),
    )
    
    return JsonResponse({"message": "Leave request created successfully", "id": leave.pk})

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

    return JsonResponse({"message": "Leave request updated successfully"})

    
