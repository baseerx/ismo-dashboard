
from datetime import date
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from sqlalchemy import text
from db import SessionLocal
from .leave_rules import compute_remaining_balance


def _current_financial_year(today=None):

    today = today or date.today()
    if today.month >= 7:
        return date(today.year, 7, 1), date(today.year + 1, 6, 30)
    return date(today.year - 1, 7, 1), date(today.year, 6, 30)


def _fetch_leave_allocation(session, leave_type):
    row = session.execute(
        text("SELECT total_leaves FROM leave_type_counts WHERE leave_type = :leave_type"),
        {"leave_type": leave_type},
    ).fetchone()
    return row[0] if row is not None else None


@require_GET
def get_leave_balance_summary(request, erpid):


    session = SessionLocal()
    try:
        emp = session.execute(text("""
            SELECT name, designation FROM employees WHERE erp_id = :erp_id AND flag = 1
        """), {"erp_id": erpid}).fetchone()
        if not emp:
            return JsonResponse({"error": "Employee not found"}, status=404)

        fy_start, fy_end = _current_financial_year()
        el_remaining = compute_remaining_balance(erpid, "Earned Leave", fy_start, fy_end)
        cl_remaining = compute_remaining_balance(erpid, "Casual Leave", fy_start, fy_end)
        el_total = _fetch_leave_allocation(session, "Earned Leave")
        cl_total = _fetch_leave_allocation(session, "Casual Leave")

        return JsonResponse({
            "employee_name": emp.name,
            "designation": emp.designation,
            "earned_leave": {"total": el_total, "remaining": el_remaining},
            "casual_leave": {"total": cl_total, "remaining": cl_remaining},
            "financial_year": {
                "start": fy_start.strftime("%d-%m-%Y"),
                "end": fy_end.strftime("%d-%m-%Y"),
            },
        }, status=200)
    finally:
        session.close()


@require_GET
def duplicate_employee_report(request):
    
    session = SessionLocal()
    try:
        rows = session.execute(text("""
            SELECT erp_id, COUNT(*) AS occurrences
            FROM employees
            WHERE flag = 1
            GROUP BY erp_id
            HAVING COUNT(*) > 1
        """)).fetchall()
        return JsonResponse({
            "duplicate_erp_ids": [
                {"erp_id": r.erp_id, "occurrences": r.occurrences} for r in rows
            ]
        }, status=200)
    finally:
        session.close()