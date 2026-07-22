from django.shortcuts import render
from django.http import JsonResponse
from .models import LeaveModel, LeaveTypeCountModel
from django.views.decorators.http import require_GET,require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
import json
from sqlalchemy import text
from db import SessionLocal
from datetime import datetime,date,timedelta
from holidays.models import Holiday
from officialwork.models import OfficialWorkModel
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
              AND status IN ('approved', 'pending')
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
       
        if leave_type.lower() == "casual leave":
            print("Checking for RR leaves for emp:", emp.erp_id)
            has_rr_leave = LeaveModel.objects.filter(
                erp_id=emp.erp_id,
                leave_type="Rest & Recreational Leave",
                start_date__lte=end_date,
                end_date__gte=start_date,
                status__in=["approved", "pending"]
            ).exists()
            
            if has_rr_leave:
                leave_count += 10
        # ------------------------------------------------
        # GET TOTAL LEAVES COUNT
        # ------------------------------------------------
        total_leaves_query = text(""" 
            SELECT total_leaves
            FROM leave_type_counts
            WHERE leave_type = :leave_type
        """)
        total_leaves_row = sessions.execute(total_leaves_query, {"leave_type": leave_type}).fetchone()
        total_leaves = total_leaves_row[0] if total_leaves_row is not None else None

        remaining_leaves = total_leaves - leave_count if total_leaves is not None else None

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
            "remaining_leaves": remaining_leaves,
            "start_date": start_date.strftime("%d-%m-%Y"),
            "end_date": end_date.strftime("%d-%m-%Y"),
        })

    sessions.close()
    return JsonResponse({"attendance": result}, status=200)

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
    # Rest & Recreational leave in the period (mirrors get_leave_balance).
    has_rr_leave = LeaveModel.objects.filter(
        erp_id=emp[1],
        leave_type="Rest & Recreational Leave",
        start_date__lte=end_date,
        end_date__gte=start_date,
        status__in=["approved", "pending"],
    ).exists()

    # Master list of every configured leave type with its annual allocation.
    all_types = sessions.execute(text("""
        SELECT leave_type, total_leaves
        FROM leave_type_counts
        ORDER BY leave_type
    """)).fetchall()

    filtered_leaves_query = text("""
        SELECT start_date, end_date
        FROM leaves
        WHERE erp_id = :erp_id
          AND status IN ('approved', 'pending')
          AND leave_type = :leave_type
          AND start_date <= :end_date
          AND end_date >= :start_date
    """)

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

        leave_count = 0
        for leave in leaves:
            actual_start = max(leave[0], start_date)
            actual_end = min(leave[1], end_date)
            leave_count += (actual_end - actual_start).days + 1

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
        leaves_query = text(""" 
            SELECT id, start_date, end_date, reason, status
            FROM leaves
            WHERE erp_id = :erp_id
              AND leave_type = :leave_type
              AND status IN ('approved', 'pending')
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
        print(leaves)
        # Process each leave record
        for leave in leaves:
            actual_start = max(leave[1], start_date)
            actual_end = min(leave[2], end_date)
            leave_count = (actual_end - actual_start).days + 1

            result.append({
                "erp_id": emp[1],
                "employee_name": emp[2],
                "section": emp[3],
                "start_date": leave[1].strftime("%Y-%m-%d"),
                "end_date": leave[2].strftime("%Y-%m-%d"),
                "leave_type": leave_type,
                "leave_count": leave_count
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

    start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_date, "%Y-%m-%d").date()

    session = SessionLocal()

    try:

        employees_query = text("""
            SELECT
                e.id AS employee_id,
                e.erp_id,
                e.name AS employee_name,
                s.name AS section_name
            FROM employees e
            INNER JOIN sections s
                ON s.id = e.section_id
            WHERE
                e.flag = 1
                AND e.section_id = :section_id
        """)

        employees = session.execute(
            employees_query,
            {"section_id": section_id}
        ).fetchall()

        result = []

        for emp in employees:

            leave_count = 0

            leaves_query = text("""
                SELECT
                    start_date,
                    end_date
                FROM leaves
                WHERE
                    erp_id = :erp_id
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

            for leave in leaves:

                overlap_start = max(leave.start_date, start_date)
                overlap_end = min(leave.end_date, end_date)

                if overlap_start <= overlap_end:
                    leave_count += (overlap_end - overlap_start).days + 1

            # Only return employees having selected leave
            if leave_count > 0:
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

        return JsonResponse({"attendance": result}, status=200)

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
        # Weekends are allowed when "sandwiched" inside a leave request
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
                    {"error": f"Leave cannot be applied on a public holiday ({day_cursor})"},
                    status=400
                )
            if day_cursor.weekday() not in (5, 6):  # not Saturday/Sunday
                has_working_day = True
            day_cursor += timedelta(days=1)

        if not has_working_day:
            return JsonResponse(
                {"error": "Leave cannot be applied only for weekend day(s)"},
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
        leave = LeaveModel.objects.create(
            erp_id=erp_id,
            employee_id=employee_id,
            head_erpid=data.get("head", 0),
            entry_made_by=data.get("entry_made_by", 0),
            leave_type=leave_type,
            reason=data.get("reason", ""),
            total_days=requested_days,
            status=data.get("status", "pending"),
            approved_by=data.get("approved_by", ""),
            start_date=start_date,
            end_date=end_date,
        )

        return JsonResponse(
            {
                "message": "Leave request created successfully",
                "leave_id": leave.pk,
                "financial_year": f"{fy_start} to {fy_end}",
                "remaining_leaves": remaining_leaves - requested_days,
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

    return JsonResponse({"message": "Leave request updated successfully"})

    
