"""Individual Detailed Report: the signed-in employee's own attendance.

The employee is taken from the sign-in token, never from the request body, so
nobody can read another employee's attendance through this endpoint - an
`erp_id` sent by the browser is ignored.

Days and averages come from the same helpers as the Section and Section Monthly
reports (section_day_records / summarize_by_employee in views.py), so all
three apply the same rules:

- A day counts towards the averages only with both a check-in and a check-out
  (at least a minute apart). Days missing either punch are left out.
- A full day of approved leave is left out. An approved short leave keeps the
  day in with only its hours exempted: leave in the first half moves the
  check-in earlier by those hours, leave in the second half moves the check-out
  later by them (exempt_short_leave).
- "No. of Days Counted" is exactly the days that went into the averages.
"""

import json
from datetime import date

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from db import SessionLocal
from jobs.permissions import identity_from_request

from .views import (
    _counts_for_average,
    exempt_short_leave,
    section_day_records,
    summarize_by_employee,
)

# One year at most per request: plenty for a personal report.
MAX_DAYS = 366


def _parse(value):
    try:
        return date.fromisoformat(str(value or "").strip()[:10])
    except ValueError:
        return None


@csrf_exempt
@require_POST
def my_detailed_report(request):
    identity, refusal = identity_from_request(request)
    if refusal:
        return JsonResponse({"error": refusal}, status=401)
    try:
        erp_id = int(identity.get("erpid") or 0)
    except (TypeError, ValueError):
        erp_id = 0
    if erp_id <= 0:
        return JsonResponse(
            {"error": "Your account is not linked to an employee record. Contact HR."},
            status=403,
        )

    try:
        data = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    fromdate, todate = _parse(data.get("fromdate")), _parse(data.get("todate"))
    if not fromdate or not todate:
        return JsonResponse({"error": "From date and to date are required."}, status=400)
    if fromdate > todate:
        return JsonResponse({"error": "From date cannot be after to date."}, status=400)
    total_days = (todate - fromdate).days + 1
    if total_days > MAX_DAYS:
        return JsonResponse(
            {"error": f"Choose a range of at most {MAX_DAYS} days."}, status=400
        )

    session = SessionLocal()
    try:
        days = section_day_records(
            session,
            {"fromdate": fromdate.isoformat(), "todate": todate.isoformat(), "erpid": erp_id},
            "AND e.erp_id = :erpid",
        )
    finally:
        session.close()

    if not days:
        return JsonResponse(
            {"error": "No active employee record was found for your account."}, status=404
        )

    for day in days:
        # Whether this day went into the averages - the same test
        # summarize_by_employee applies - so the page can show which did.
        counted = not day.get("on_leave") and _counts_for_average(
            day["checkin_time"], day["checkout_time"]
        )
        day["counted_for_average"] = counted
        if counted and day.get("short_leave_start"):
            checkin, checkout = exempt_short_leave(
                day["checkin_time"], day["checkout_time"],
                day["short_leave_start"], day["short_leave_end"],
            )
            day["adjusted_checkin"], day["adjusted_checkout"] = checkin, checkout

    summary = summarize_by_employee(days, total_days)[0]

    first = days[0]
    return JsonResponse(
        {
            "employee": {
                "erp_id": first["erp_id"],
                "name": first["name"],
                "designation": first["designation"],
                "grade": first["grade"],
                "section": first["section"],
            },
            "summary": {
                "days": summary["days"],
                "checkin_count": summary["checkin_count"],
                "checkout_count": summary["checkout_count"],
                "avg_checkin": summary["avg_checkin"],
                "avg_checkout": summary["avg_checkout"],
                "avg_worked": summary["avg_worked"],
                "avg_days": summary["avg_days"],
            },
            "days": days,
        },
        status=200,
    )
