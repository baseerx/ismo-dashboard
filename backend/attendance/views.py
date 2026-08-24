from django.shortcuts import render
from .models import Attendance  # Assuming you have an Attendance model defined
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from datetime import date, datetime, time, timedelta
from sqlalchemy import text
from django.views.decorators.csrf import csrf_exempt
from dotenv import load_dotenv
import os
import json
import requests  # Ensure you have requests installed in your environment
# Assuming you have a SessionLocal defined for database access
from db import SessionLocal
# Create your views here.
from leaves.models import LeaveModel
from holidays.models import Holiday

load_dotenv()  # Load environment variables from .env file
class AttendanceView:
    @require_GET  # Ensure this view only responds to GET requests
    def get(request):
        attendance_records = Attendance.objects.all()  # Fetch all attendance records
        records = attendance_records.values(
            'uid', 'user_id', 'timestamp', 'status', 'punch'
        )
        attendance_list = list(records)
        # Return as JSON response
        return JsonResponse(attendance_list, safe=False)

    @require_GET
    def todays_attendance(request):
        today = datetime.now().date()
        session = SessionLocal()
        records = []

        try:
            query = text("""
                SELECT
                    e.id AS id,
                    e.erp_id AS erp_id,
                    e.name AS name,
                    d.title AS designation,
                    s.name AS section,
                    a.uid AS uid,
                    e.hris_id AS user_id,
                    a.timestamp AS timestamp,
                    a.status AS status,
                    g.name AS grade,
                    a.lateintime AS lateintime
                FROM employees e
                LEFT JOIN sections s ON s.id = e.section_id
                LEFT JOIN designations d ON d.id = e.designation_id
                LEFT JOIN grades g ON g.id = e.grade_id
                LEFT JOIN attendance a
                    ON e.hris_id = a.user_id
                    AND CAST(a.timestamp AS DATE) = :today
                WHERE e.flag = 1
                ORDER BY g.name DESC
            """)

            result = session.execute(query, {"today": today}).fetchall()

            for row in result:

                flag = "Absent"

                if row.uid is not None:
                    flag = "Present"

                else:

                    # Check Leave
                    leave_result = session.execute(text("""
                        SELECT leave_type
                        FROM leaves
                        WHERE erp_id = :erp_id
                        AND CAST(start_date AS DATE) <= CAST(:att_date AS DATE)
                        AND CAST(end_date AS DATE) >= CAST(:att_date AS DATE)
                    """), {
                        "erp_id": row.erp_id,
                        "att_date": today
                    }).first()

                    # Check Official Work
                    official_work = session.execute(text("""
                        SELECT leave_type
                        FROM official_work_leaves
                        WHERE erp_id = :erp_id
                        AND CAST(start_date AS DATE) <= CAST(:att_date AS DATE)
                        AND CAST(end_date AS DATE) >= CAST(:att_date AS DATE)
                    """), {
                        "erp_id": row.erp_id,
                        "att_date": today
                    }).first()

                    if leave_result:
                        flag = leave_result.leave_type

                    elif official_work:
                        flag = official_work.leave_type

                    else:

                        # Check Public Holiday
                        holiday_result = session.execute(text("""
                            SELECT name
                            FROM public_holidays
                            WHERE CAST(date AS DATE) = :att_date
                        """), {
                            "att_date": today
                        }).first()

                        if holiday_result:
                            flag = holiday_result.name

                        # Saturday = 5, Sunday = 6
                        elif today.weekday() in (5, 6):
                            flag = "Weekend"

                        else:
                            flag = "Absent"

                records.append({
                    "id": row.id,
                    "erp_id": row.erp_id,
                    "name": row.name,
                    "designation": row.designation,
                    "grade": row.grade,
                    "section": row.section,
                    "uid": row.uid,
                    "user_id": row.user_id,
                    "timestamp": "-" if row.timestamp is None else row.timestamp,
                    "late": (
                        "early"
                        if row.status == "Early Checked Out"
                        else "-"
                        if row.timestamp is None
                        else row.lateintime
                    ),
                    "status": "-" if row.status is None else row.status,
                    "flag": flag
                })

            return JsonResponse(records, safe=False)

        finally:
            session.close()

    @require_GET
    def attendance_overview(request, erpid):
        today = datetime.now().date()
        session = SessionLocal()
        section_query = text("""
            SELECT e.hris_id AS hrisid, s.name AS name
            FROM dbo.employees e
            JOIN dbo.sections s ON e.section_id = s.id
            WHERE e.erp_id = :erpid
        """)
        section_result = session.execute(section_query, {"erpid": erpid})
        row = section_result.first()
        if row:
            section_data = {"hrisid": row.hrisid, "name": row.name}
            query = text("""
                SELECT
                    e.id AS id,
                    e.erp_id AS erp_id,
                    e.name AS name,
                    d.title AS designation,
                    s.name AS section,
                    g.name AS grade,
                    MAX(CASE WHEN a.status = 'Checked In' THEN a.timestamp END) AS checkin_time,
                    MAX(CASE WHEN a.status IN ('Checked Out', 'Early Checked Out') THEN a.timestamp END) AS checkout_time
                FROM employees e
                LEFT JOIN sections s ON s.id = e.section_id
                LEFT JOIN designations d ON d.id = e.designation_id
                LEFT JOIN grades g ON g.id = e.grade_id
                LEFT JOIN attendance a ON e.hris_id = a.user_id 
                    AND CAST(a.timestamp AS DATE) = :today
                WHERE e.section_id = (SELECT id FROM sections WHERE name = :section_name) and e.flag = 1
                GROUP BY 
                    e.id,
                    e.erp_id,
                    e.name,
                    d.title,
                    g.name,
                    s.name,
                    e.hris_id
                ORDER BY g.name desc
            """)

            result = session.execute(
                query, {"today": today, "section_name": row.name}).fetchall()
            records = []
            for row in result:
                # Integrate leave and holiday check for each employee for today
                flag = 'Absent'
                leave_result = session.execute(text("""
                        SELECT leave_type FROM leaves
                        WHERE erp_id = :erp_id
                        AND CAST(start_date AS DATE) <= CAST(:att_date AS DATE)
                        AND CAST(end_date AS DATE) >= CAST(:att_date AS DATE)
                    """), {"erp_id": row.erp_id, "att_date": today}).first()
                official_work = session.execute(text("""
                                        SELECT leave_type FROM official_work_leaves
                                        WHERE erp_id = :erp_id
                                        AND CAST(start_date AS DATE) <= CAST(:att_date AS DATE)
                                        AND CAST(end_date AS DATE) >= CAST(:att_date AS DATE)
                                    """), {"erp_id": row.erp_id, "att_date": today}).first()
                if row.checkin_time is not None or row.checkout_time is not None:
                    flag = 'Present'
                else:
                    if leave_result:
                        flag = leave_result.leave_type
                    elif official_work:
                        flag = official_work.leave_type
                    else:
                        holiday_result = session.execute(text("""
                            SELECT name FROM public_holidays
                            WHERE CAST(date AS DATE) = :att_date
                        """), {"att_date": today}).first()
                        if holiday_result:
                            flag = holiday_result.name
                        else:
                            flag = 'Absent'
                records.append({
                    'id': row.id,
                    'erp_id': row.erp_id,
                    'name': row.name,
                    'designation': row.designation,
                    'section': row.section,
                    'grade': row.grade,
                    'checkin_time': row.checkin_time if row.checkin_time is not None else '-',
                    'checkout_time': row.checkout_time if row.checkout_time is not None else '-',
                    'flag': flag
                })
            return JsonResponse(records, safe=False)
        else:
            section_data = None
        return JsonResponse({"section": section_data}, safe=False)

    @csrf_exempt
    @require_POST
    def attendance_individual(request):
        data = json.loads(request.body)
        erpid = data.get('erpid')
        if not erpid:
            return JsonResponse({"error": "erpid is required"}, status=400)

        fromdate = data.get('fromdate')
        todate = data.get('todate')

        session = SessionLocal()
        records = []
        try:
            query = text("""
                WITH date_range AS (
                    SELECT 
                        DATEADD(DAY, v.number, :fromdate) AS the_date
                    FROM master..spt_values v
                    WHERE v.type = 'P'
                        AND DATEADD(DAY, v.number, :fromdate) <= :todate
                )
                SELECT
                    dr.the_date,
                    e.id AS id,
                    e.erp_id AS erp_id,
                    e.name AS name,
                    d.title AS designation,
                    s.name AS section,
                    g.name AS grade,
                    a.uid AS uid,
                    e.hris_id AS user_id,
                    a.timestamp AS timestamp,
                    a.status AS status,
                    a.lateintime AS lateintime,
                    a.punch AS punch
                FROM date_range dr
                JOIN employees e ON 1=1
                LEFT JOIN sections s ON s.id = e.section_id
                LEFT JOIN designations d ON d.id = e.designation_id
                LEFT JOIN grades g ON g.id = e.grade_id
                LEFT JOIN attendance a 
                    ON e.hris_id = a.user_id 
                    AND CAST(a.timestamp AS DATE) = dr.the_date
                WHERE e.erp_id = :erpid AND e.flag = 1
                ORDER BY dr.the_date,
                         e.id,
                         CASE 
                             WHEN a.status = 'Checked In' THEN 0
                             WHEN a.status = 'Checked Out' THEN 1
                             ELSE 2
                         END,
                         a.timestamp
            """)

            result = session.execute(
                query, {"fromdate": fromdate, "todate": todate, "erpid": erpid})
            rows = result.fetchall()  # Ensure results are consumed before issuing new queries
            flag = 'Absent'
            for row in rows:
                check_in_deadline=time(8,30)
                check_out_deadline=time(16,0)
                if row.status == 'Checked In':
                    punch_time = row.timestamp.time() if row.timestamp else None
                    if punch_time and punch_time > check_in_deadline:
                        late_status = 'Late'
                    else:
                        late_status = 'On time'


                elif row.status == 'Checked Out':
                    punch_time = row.timestamp.time() if row.timestamp else None
                    if punch_time and punch_time < check_out_deadline:
                        late_status = 'Early'
                    else:
                        late_status = 'On time'
                else:
                    late_status = 'Early'
                    
                leave_result = session.execute(text("""
                        SELECT leave_type FROM leaves
                        WHERE erp_id = :erp_id
                        AND CAST(start_date AS DATE) <= CAST(:att_date AS DATE)
                        AND CAST(end_date AS DATE) >= CAST(:att_date AS DATE)
                    """), {"erp_id": row.erp_id, "att_date": row.the_date}).first()
                
                official_work = session.execute(text("""
                                        SELECT leave_type FROM official_work_leaves
                                        WHERE erp_id = :erp_id
                                        AND CAST(start_date AS DATE) <= CAST(:att_date AS DATE)
                                        AND CAST(end_date AS DATE) >= CAST(:att_date AS DATE)
                                    """), {"erp_id": row.erp_id, "att_date": row.the_date}).first()

                if row.uid is not None:
                       flag = 'Present'

                elif row.the_date:
                        # Check for leave on that specific date
                        if leave_result:
                            flag = leave_result.leave_type

                        elif official_work:
                            flag = official_work.leave_type

                        else:
                            # Check for holiday on that date
                            holiday_result = session.execute(text("""
                                SELECT name FROM public_holidays
                                WHERE CAST(date AS DATE) = :att_date
                            """), {"att_date": row.the_date}).first()

                            if holiday_result:
                                flag = holiday_result.name

                            # Weekend check (Saturday=5, Sunday=6)
                            elif row.the_date.weekday() in [5, 6]:
                                flag = 'Weekend'

                            else:
                                flag = 'Absent'

                records.append({
                    'id': row.id,
                    'erp_id': row.erp_id,
                    'name': row.name,
                    'designation': row.designation,
                    'section': row.section,
                    'grade': row.grade,
                    'uid': row.uid,
                    'user_id': row.user_id,
                    'timestamp': row.the_date if row.timestamp is None else row.timestamp,
                    'late': '-' if flag == 'Absent' else late_status,
                    'flag': flag,
                    'status': '-' if row.status is None else row.status,
                    'punch': row.punch
                })

            return JsonResponse(records, safe=False)
        finally:
            session.close()

    @csrf_exempt
    @require_POST
    def attendance_history(request):
        data = json.loads(request.body)
        fromdate = data.get('fromdate')
        todate = data.get('todate')

        session = SessionLocal()
        records = []
        try:
            query = text("""
                WITH date_range AS (
                    SELECT 
                        DATEADD(DAY, v.number, :fromdate) AS the_date
                    FROM master..spt_values v
                    WHERE v.type = 'P'
                        AND DATEADD(DAY, v.number, :fromdate) <= :todate
                )
                SELECT
                    dr.the_date,
                    e.id AS id,
                    e.erp_id AS erp_id,
                    e.name AS name,
                    d.title AS designation,
                    g.name AS grade,
                    s.name AS section,
                    a.uid AS uid,
                    e.hris_id AS user_id,
                    a.timestamp AS timestamp,
                    a.status AS status,
                    a.lateintime AS lateintime,
                    a.punch AS punch
                FROM date_range dr
                JOIN employees e ON 1=1
                LEFT JOIN sections s ON s.id = e.section_id
                LEFT JOIN designations d ON d.id = e.designation_id
                LEFT JOIN grades g ON g.id = e.grade_id
                LEFT JOIN attendance a 
                    ON e.hris_id = a.user_id 
                    AND CAST(a.timestamp AS DATE) = dr.the_date
                WHERE e.flag = 1
                ORDER BY g.name DESC
            """)

            result = session.execute(
                query, {"fromdate": fromdate, "todate": todate})
            rows = result.fetchall()
            for row in rows:
                flag = 'Absent'
                check_in_deadline = time(8, 30)
                check_out_deadline = time(16, 0)
                if row.status == 'Checked In':
                    punch_time = row.timestamp.time() if row.timestamp else None
                    if punch_time and punch_time > check_in_deadline:
                        late_status = 'Late'
                    else:
                        late_status = 'On time'

                elif row.status == 'Checked Out':
                    punch_time = row.timestamp.time() if row.timestamp else None
                    if punch_time and punch_time < check_out_deadline:
                        late_status = 'Early'
                    else:
                        late_status = 'On time'
                else:
                    late_status = 'Early'
                leave_result = session.execute(text("""
                        SELECT leave_type FROM leaves
                        WHERE erp_id = :erp_id
                        AND CAST(start_date AS DATE) <= CAST(:att_date AS DATE)
                        AND CAST(end_date AS DATE) >= CAST(:att_date AS DATE)
                    """), {"erp_id": row.erp_id, "att_date": row.the_date}).first()
                official_work = session.execute(text("""
                                        SELECT leave_type FROM official_work_leaves
                                        WHERE erp_id = :erp_id
                                        AND CAST(start_date AS DATE) <= CAST(:att_date AS DATE)
                                        AND CAST(end_date AS DATE) >= CAST(:att_date AS DATE)
                                    """), {"erp_id": row.erp_id, "att_date": row.the_date}).first()

                if row.uid is not None:
                    flag = 'Present'
                elif row.the_date:
                    if leave_result:
                        flag = leave_result.leave_type
                    elif official_work:
                        flag = official_work.leave_type
                    else:
                        holiday_result = session.execute(text("""
                            SELECT name FROM public_holidays
                            WHERE CAST(date AS DATE) = :att_date
                        """), {"att_date": row.the_date}).first()
                        if holiday_result:
                            flag = holiday_result.name
                        else:
                            flag = 'Absent'

                records.append({
                    'id': row.id,
                    'erp_id': row.erp_id,
                    'name': row.name,
                    'designation': row.designation,
                    'grade': row.grade,
                    'section': row.section,
                    'uid': row.uid,
                    'user_id': row.user_id,
                    'timestamp': row.the_date if row.timestamp is None else row.timestamp,
                    'late': '-' if flag=='Absent' else late_status,
                    'flag': flag,
                    'status': '-' if row.status is None else row.status,
                    'punch': row.punch
                })
            return JsonResponse(records, safe=False)
        finally:
            session.close()
            
    @csrf_exempt
    @require_POST
    def attendance_detailed(request):
        data = json.loads(request.body)
        fromdate = data.get('fromdate')
        todate = data.get('todate')

        session = SessionLocal()
        records = []

        try:
            query = text("""
                WITH date_range AS (
                    SELECT
                        DATEADD(DAY, v.number, :fromdate) AS the_date
                    FROM master..spt_values v
                    WHERE v.type = 'P'
                        AND DATEADD(DAY, v.number, :fromdate) <= :todate
                )
                SELECT
                    dr.the_date,
                    e.erp_id AS erp_id,
                    e.name AS name,
                    d.title AS designation,
                    g.name AS grade,
                    s.name AS section,
                    MAX(CASE WHEN a.status = 'Checked In' THEN a.timestamp END) AS checkin_time,
                    MAX(CASE WHEN a.status IN ('Checked Out', 'Early Checked Out') THEN a.timestamp END) AS checkout_time
                FROM date_range dr
                JOIN employees e ON 1 = 1
                LEFT JOIN sections s
                    ON s.id = e.section_id
                LEFT JOIN designations d
                    ON d.id = e.designation_id
                LEFT JOIN grades g
                    ON g.id = e.grade_id
                LEFT JOIN attendance a
                    ON e.hris_id = a.user_id
                    AND CAST(a.timestamp AS DATE) = dr.the_date
                WHERE e.flag = 1
                GROUP BY
                    dr.the_date,
                    e.id,
                    e.erp_id,
                    e.name,
                    d.title,
                    g.name,
                    s.name,
                    e.hris_id
                ORDER BY
                    g.name DESC,
                    dr.the_date,
                    e.erp_id
            """)

            result = session.execute(
                query,
                {
                    "fromdate": fromdate,
                    "todate": todate
                }
            )

            rows = result.fetchall()

            for row in rows:

                flag = "Absent"

                leave_result = session.execute(text("""
                    SELECT leave_type
                    FROM leaves
                    WHERE erp_id = :erp_id
                    AND CAST(start_date AS DATE) <= CAST(:att_date AS DATE)
                    AND CAST(end_date AS DATE) >= CAST(:att_date AS DATE)
                """), {
                    "erp_id": row.erp_id,
                    "att_date": row.the_date
                }).first()

                official_work = session.execute(text("""
                    SELECT leave_type
                    FROM official_work_leaves
                    WHERE erp_id = :erp_id
                    AND CAST(start_date AS DATE) <= CAST(:att_date AS DATE)
                    AND CAST(end_date AS DATE) >= CAST(:att_date AS DATE)
                """), {
                    "erp_id": row.erp_id,
                    "att_date": row.the_date
                }).first()

                if row.checkin_time is not None:
                    flag = "Present"

                elif row.checkin_time is None and row.checkout_time is None:

                    if leave_result:
                        flag = leave_result.leave_type

                    elif official_work:
                        flag = official_work.leave_type

                    else:

                        holiday_result = session.execute(text("""
                            SELECT name
                            FROM public_holidays
                            WHERE CAST(date AS DATE) = :att_date
                        """), {
                            "att_date": row.the_date
                        }).first()

                        if holiday_result:
                            flag = holiday_result.name

                        # Saturday = 5, Sunday = 6
                        elif row.the_date.weekday() in (5, 6):
                            flag = "Weekend"

                        else:
                            flag = "Absent"

                # if row.erp_id == 471:
                #     print(row.the_date, flag)

                records.append({
                    "erp_id": row.erp_id,
                    "name": row.name,
                    "designation": row.designation,
                    "grade": row.grade,
                    "section": row.section,
                    "checkout_time": row.checkout_time if row.checkout_time is not None else "-",
                    "checkin_time": row.checkin_time if row.checkin_time is not None else "-",
                    "timestamp": row.the_date,
                    "late": flag,
                })

            return JsonResponse(records, safe=False)

        finally:
            session.close()

    @csrf_exempt
    @require_POST
    def attendance_team_level(request):
        data = json.loads(request.body)
        fromdate = data.get('fromdate')
        todate = data.get('todate')
        erp_id = data.get('erp_id')

        session = SessionLocal()
        records = []
        try:
            query = text("""
                SELECT
                    e.erp_id AS erp_id,
                    e.name AS name,
                    d.title AS designation,
                    g.name AS grade,
                    s.name AS section,
                    MAX(CASE WHEN a.status = 'Checked In' THEN a.lateintime END) AS lateintime,
                    CAST(a.timestamp AS DATE) AS timestamp,
                    MIN(CASE WHEN a.status = 'Checked In' THEN a.timestamp END) AS checkin_time,
                    MAX(CASE WHEN a.status IN ('Checked Out', 'Early Checked Out') THEN a.timestamp END) AS checkout_time
                FROM employees e
                LEFT JOIN sections s ON s.id = e.section_id
                LEFT JOIN designations d ON d.id = e.designation_id
                LEFT JOIN grades g ON g.id = e.grade_id
                LEFT JOIN attendance a 
                    ON e.hris_id = a.user_id 
                    AND CAST(a.timestamp AS DATE) BETWEEN :fromdate AND :todate
                WHERE e.flag = 1 
                    AND e.section_id = (SELECT section_id FROM employees WHERE erp_id = :erpid)
                    AND e.grade_id <= (SELECT grade_id FROM employees WHERE erp_id = :erpid)
                GROUP BY 
                    e.erp_id, 
                    e.name, 
                    d.title, 
                    g.name, 
                    s.name, 
                    e.grade_id,
                    CAST(a.timestamp AS DATE)
                -- Most senior first: G-11, then G-10, down to G-01. Ordered by
                -- grade_id rather than the grade's name so it stays numeric if
                -- a grade is ever labelled without its leading zero.
                ORDER BY e.grade_id DESC, e.name, timestamp
            """)

            result = session.execute(
                query, {"fromdate": fromdate, "todate": todate, "erpid": erp_id})
            rows = result.fetchall()
          
            for row in rows:
                flag = 'Absent'
                att_date = row.timestamp if row.timestamp else None
                leave_result = session.execute(text("""
                        SELECT leave_type FROM leaves
                        WHERE erp_id = :erp_id
                        AND CAST(start_date AS DATE) <= CAST(:att_date AS DATE)
                        AND CAST(end_date AS DATE) >= CAST(:att_date AS DATE)
                    """), {"erp_id": row.erp_id, "att_date": att_date}).first()
                official_work = session.execute(text("""
                                        SELECT leave_type FROM official_work_leaves
                                        WHERE erp_id = :erp_id
                                        AND CAST(start_date AS DATE) <= CAST(:att_date AS DATE)
                                        AND CAST(end_date AS DATE) >= CAST(:att_date AS DATE)
                                    """), {"erp_id": row.erp_id, "att_date": att_date}).first()

                if att_date is not None:
                    flag = 'Present'
                elif att_date:
                    if leave_result:
                        flag = leave_result.leave_type
                    elif official_work:
                        flag = official_work.leave_type
                    else:
                        holiday_result = session.execute(text("""
                            SELECT name FROM public_holidays
                            WHERE CAST(date AS DATE) = :att_date
                        """), {"att_date": att_date}).first()
                        if holiday_result:
                            flag = holiday_result.name
                        else:
                            flag = 'Absent'

                records.append({
                    'erp_id': row.erp_id,
                    'name': row.name,
                    'designation': row.designation,
                    'grade': row.grade,
                    'section': row.section,
                    'checkout_time': row.checkout_time if row.checkout_time is not None else '-',
                    'checkin_time': row.checkin_time if row.checkin_time is not None else '-',
                    'timestamp': row.timestamp if row.timestamp is not None else '-',
                    'late': '-' if flag=='Absent' else flag,
                    'lateintime': row.lateintime if row.lateintime is not None else '-',
                })
            return JsonResponse(records, safe=False)
        finally:
            session.close()
    
  
    @csrf_exempt
    @require_POST
    def attendance_total_absent(request):
        data = json.loads(request.body)
        fromdate = data.get("fromdate")
        todate = data.get("todate")

        session = SessionLocal()
        records = []

        try:
            query = text("""
                WITH date_range AS (
                    SELECT
                        DATEADD(DAY, v.number, :fromdate) AS the_date
                    FROM master..spt_values v
                    WHERE v.type = 'P'
                    AND DATEADD(DAY, v.number, :fromdate) <= :todate
                )

                SELECT
                    dr.the_date AS timestamp,
                    e.erp_id,
                    e.name,
                    d.title AS designation,
                    g.name AS grade,
                    s.name AS section

                FROM date_range dr
                CROSS JOIN employees e

                LEFT JOIN sections s
                    ON s.id = e.section_id

                LEFT JOIN designations d
                    ON d.id = e.designation_id

                LEFT JOIN grades g
                    ON g.id = e.grade_id

                WHERE
                    e.flag = 1

                    AND NOT EXISTS
                    (
                        SELECT 1
                        FROM attendance a
                        WHERE a.user_id = e.hris_id
                        AND CAST(a.timestamp AS DATE)=dr.the_date
                    )

                    AND NOT EXISTS
                    (
                        SELECT 1
                        FROM leaves l
                        WHERE l.erp_id=e.erp_id
                        AND CAST(l.start_date AS DATE)<=dr.the_date
                        AND CAST(l.end_date AS DATE)>=dr.the_date
                    )

                    AND NOT EXISTS
                    (
                        SELECT 1
                        FROM official_work_leaves ow
                        WHERE ow.erp_id=e.erp_id
                        AND CAST(ow.start_date AS DATE)<=dr.the_date
                        AND CAST(ow.end_date AS DATE)>=dr.the_date
                    )

                    AND NOT EXISTS
                    (
                        SELECT 1
                        FROM public_holidays ph
                        WHERE CAST(ph.date AS DATE)=dr.the_date
                    )

                ORDER BY
                    dr.the_date,
                    g.name DESC,
                    e.erp_id
            """)

            rows = session.execute(
                query,
                {
                    "fromdate": fromdate,
                    "todate": todate,
                },
            ).fetchall()

            for row in rows:
                records.append({
                    "erp_id": row.erp_id,
                    "name": row.name,
                    "designation": row.designation,
                    "grade": row.grade,
                    "section": row.section,
                    "timestamp": row.timestamp,
                    "late": "Absent",
                })

            return JsonResponse(records, safe=False)

        finally:
            session.close()
    
    @csrf_exempt
    @require_POST
    def attendance_detailed_absent_report(request):
        data = json.loads(request.body)
        fromdate = data.get("fromdate")
        todate = data.get("todate")

        session = SessionLocal()

        try:

            query = text("""
            WITH date_range AS
            (
                SELECT DATEADD(DAY, v.number, :fromdate) AS att_date
                FROM master..spt_values v
                WHERE v.type = 'P'
                AND DATEADD(DAY, v.number, :fromdate) <= :todate
            ),

            employees_data AS
            (
                SELECT
                    e.erp_id,
                    e.hris_id,
                    ISNULL(s.name, '-') AS section
                FROM employees e
                LEFT JOIN sections s
                    ON s.id = e.section_id
                WHERE e.flag = 1
            ),

            attendance_days AS
            (
                SELECT DISTINCT
                    user_id,
                    CAST(timestamp AS DATE) AS att_date
                FROM attendance
                WHERE timestamp >= :fromdate
                AND timestamp < DATEADD(DAY, 1, :todate)
            ),

            leave_days AS
            (
                SELECT
                    erp_id,
                    CAST(start_date AS DATE) AS start_date,
                    CAST(end_date AS DATE) AS end_date
                FROM leaves
                WHERE status='approved'
                AND end_date >= :fromdate
                AND start_date <= :todate
            ),

            official_days AS
            (
                SELECT
                    erp_id,
                    CAST(start_date AS DATE) AS start_date,
                    CAST(end_date AS DATE) AS end_date
                FROM official_work_leaves
                WHERE status='approved'
                AND end_date >= :fromdate
                AND start_date <= :todate
            ),

            holiday_days AS
            (
                SELECT
                    CAST(date AS DATE) AS holiday_date
                FROM public_holidays
                WHERE date BETWEEN :fromdate AND :todate
            )

            SELECT

                dr.att_date AS attendance_date,

                ed.section,

                COUNT(*) AS total_employees,

                SUM(
                    CASE
                        WHEN a.user_id IS NOT NULL
                        THEN 1
                        ELSE 0
                    END
                ) AS total_present,

                SUM(
                    CASE
                        WHEN l.erp_id IS NOT NULL
                        THEN 1
                        ELSE 0
                    END
                ) AS total_leave,

                SUM(
                    CASE
                        WHEN ow.erp_id IS NOT NULL
                        THEN 1
                        ELSE 0
                    END
                ) AS total_official_work,

                SUM(
                    CASE

                        -- Present
                        WHEN a.user_id IS NOT NULL
                        THEN 0

                        -- Leave
                        WHEN l.erp_id IS NOT NULL
                        THEN 0

                        -- Official Work
                        WHEN ow.erp_id IS NOT NULL
                        THEN 0

                        -- Holiday
                        WHEN h.holiday_date IS NOT NULL
                        THEN 0

                        -- Saturday
                        WHEN DATEPART(WEEKDAY, dr.att_date) = 7
                        THEN 0

                        -- Sunday
                        WHEN DATEPART(WEEKDAY, dr.att_date) = 1
                        THEN 0

                        ELSE 1

                    END
                ) AS total_absent

            FROM employees_data ed

            CROSS JOIN date_range dr

            LEFT JOIN attendance_days a
                ON a.user_id = ed.hris_id
            AND a.att_date = dr.att_date

            LEFT JOIN leave_days l
                ON l.erp_id = ed.erp_id
            AND dr.att_date BETWEEN l.start_date AND l.end_date

            LEFT JOIN official_days ow
                ON ow.erp_id = ed.erp_id
            AND dr.att_date BETWEEN ow.start_date AND ow.end_date

            LEFT JOIN holiday_days h
                ON h.holiday_date = dr.att_date

            GROUP BY
                dr.att_date,
                ed.section

            ORDER BY
                dr.att_date,
                ed.section
            """)

            rows = session.execute(
                query,
                {
                    "fromdate": fromdate,
                    "todate": todate,
                }
            ).fetchall()

            records = []

            for row in rows:

                records.append({

                    "date": row.attendance_date,
                    "section": row.section,
                    "total_employees": row.total_employees,
                    "total_present": row.total_present,
                    "total_leave": row.total_leave,
                    "total_official_work": row.total_official_work,
                    "total_absent": row.total_absent,

                    "status": (
                        f"Present: {row.total_present}, "
                        f"Leave: {row.total_leave}, "
                        f"Official Work: {row.total_official_work}, "
                        f"Absent: {row.total_absent}"
                    )

                })

            return JsonResponse(records, safe=False)

        finally:
            session.close()

    @csrf_exempt
    @require_POST
    def attendance_individual_user(request):
        data = json.loads(request.body)
        fromdate = data.get('fromdate')
        todate = data.get('todate')
        erp_id = data.get('erp_id')

        session = SessionLocal()
        records = []
        try:
            query = text("""
                SELECT
                    e.erp_id AS erp_id,
                    e.name AS name,
                    d.title AS designation,
                    g.name AS grade,
                    s.name AS section,
                    MAX(CASE WHEN a.status = 'Checked In' THEN a.lateintime END) AS lateintime,
                    CAST(a.timestamp AS DATE) AS timestamp,
                    MIN(CASE WHEN a.status = 'Checked In' THEN a.timestamp END) AS checkin_time,
                    MAX(CASE WHEN a.status IN ('Checked Out', 'Early Checked Out') THEN a.timestamp END) AS checkout_time
                FROM employees e
                LEFT JOIN sections s ON s.id = e.section_id
                LEFT JOIN designations d ON d.id = e.designation_id
                LEFT JOIN grades g ON g.id = e.grade_id
                LEFT JOIN attendance a 
                    ON e.hris_id = a.user_id 
                    AND CAST(a.timestamp AS DATE) BETWEEN :fromdate AND :todate
                WHERE e.flag = 1 
                    AND e.erp_id = :erpid
                GROUP BY 
                    e.erp_id, 
                    e.name, 
                    d.title, 
                    g.name, 
                    s.name, 
                    CAST(a.timestamp AS DATE)
                ORDER BY timestamp
            """)

            result = session.execute(
                query, {"fromdate": fromdate, "todate": todate, "erpid": erp_id})
            rows = result.fetchall()
          
            for row in rows:
                flag = 'Absent'
                att_date = row.timestamp if row.timestamp else None
                leave_result = session.execute(text("""
                        SELECT leave_type FROM leaves
                        WHERE erp_id = :erp_id
                        AND CAST(start_date AS DATE) <= CAST(:att_date AS DATE)
                        AND CAST(end_date AS DATE) >= CAST(:att_date AS DATE)
                    """), {"erp_id": row.erp_id, "att_date": att_date}).first()
                official_work = session.execute(text("""
                                        SELECT leave_type FROM official_work_leaves
                                        WHERE erp_id = :erp_id
                                        AND CAST(start_date AS DATE) <= CAST(:att_date AS DATE)
                                        AND CAST(end_date AS DATE) >= CAST(:att_date AS DATE)
                                    """), {"erp_id": row.erp_id, "att_date": att_date}).first()

                if att_date is not None:
                    flag = 'Present'
                elif att_date:
                    if leave_result:
                        flag = leave_result.leave_type
                    elif official_work:
                        flag = official_work.leave_type
                    else:
                        holiday_result = session.execute(text("""
                            SELECT name FROM public_holidays
                            WHERE CAST(date AS DATE) = :att_date
                        """), {"att_date": att_date}).first()
                        if holiday_result:
                            flag = holiday_result.name
                        else:
                            flag = 'Absent'

                records.append({
                    'erp_id': row.erp_id,
                    'name': row.name,
                    'designation': row.designation,
                    'grade': row.grade,
                    'section': row.section,
                    'checkout_time': row.checkout_time if row.checkout_time is not None else '-',
                    'checkin_time': row.checkin_time if row.checkin_time is not None else '-',
                    'timestamp': row.timestamp if row.timestamp is not None else '-',
                    'late': '-' if flag=='Absent' else flag,
                    'lateintime': row.lateintime if row.lateintime is not None else '-',
                })
            return JsonResponse(records, safe=False)
        finally:
            session.close()

    @csrf_exempt
    @require_POST
    def attendance_section_monthly(request):
        """
        Monthly attendance for every employee of the requested section.
        Returns one row per (employee, day) with the day's first check-in and
        last check-out, so the frontend can pivot it into a day-wise grid.
        """
        data = json.loads(request.body.decode("utf-8"))
        erp_id = data.get("erp_id")
        fromdate = data.get("fromdate")
        todate = data.get("todate")
        # Optional section filter:
        #   omitted / ""  -> the requesting user's own section (default)
        #   0 / "all"     -> every section
        #   <id>          -> that section only
        section_id = data.get("section_id")

        if not erp_id or not fromdate or not todate:
            return JsonResponse(
                {"error": "erp_id, fromdate and todate are required"}, status=400
            )

        params = {"fromdate": fromdate, "todate": todate}
        section_choice = (
            str(section_id).strip().lower() if section_id is not None else ""
        )

        if section_choice in ("", "none", "null"):
            section_filter = (
                "AND e.section_id = "
                "(SELECT section_id FROM employees WHERE erp_id = :erpid)"
            )
            params["erpid"] = erp_id
        elif section_choice in ("0", "all"):
            section_filter = ""  # every section
        else:
            try:
                params["section_id"] = int(section_choice)
            except ValueError:
                return JsonResponse(
                    {"error": "section_id must be a section id, 0 or 'all'"},
                    status=400,
                )
            section_filter = "AND e.section_id = :section_id"

        session = SessionLocal()
        records = []
        try:
            query = text(f"""
                WITH date_range AS (
                    SELECT DATEADD(DAY, v.number, :fromdate) AS the_date
                    FROM master..spt_values v
                    WHERE v.type = 'P'
                        AND DATEADD(DAY, v.number, :fromdate) <= :todate
                ),
                section_employees AS (
                    SELECT
                        e.id,
                        e.erp_id,
                        e.name,
                        e.hris_id,
                        e.section_id,
                        e.designation_id,
                        e.grade_id
                    FROM employees e
                    WHERE e.flag = 1
                        {section_filter}
                ),
                att AS (
                    -- Pre-aggregate the month's punches once, filtered by a sargable
                    -- timestamp range and to this section's employees only.
                    SELECT
                        a.user_id,
                        CAST(a.timestamp AS DATE) AS att_date,
                        MIN(CASE WHEN a.status = 'Checked In' THEN a.timestamp END) AS checkin_time,
                        MAX(CASE WHEN a.status IN ('Checked Out', 'Early Checked Out') THEN a.timestamp END) AS checkout_time
                    FROM attendance a
                    WHERE a.timestamp >= :fromdate
                        AND a.timestamp < DATEADD(DAY, 1, :todate)
                        AND a.user_id IN (SELECT hris_id FROM section_employees)
                    GROUP BY a.user_id, CAST(a.timestamp AS DATE)
                ),
                leave_days AS (
                    SELECT erp_id, leave_type,
                           CAST(start_date AS DATE) AS start_date,
                           CAST(end_date AS DATE) AS end_date
                    FROM leaves
                    WHERE status = 'approved'
                        AND end_date >= :fromdate
                        AND start_date <= :todate
                ),
                official_days AS (
                    SELECT erp_id, leave_type,
                           CAST(start_date AS DATE) AS start_date,
                           CAST(end_date AS DATE) AS end_date
                    FROM official_work_leaves
                    WHERE status = 'approved'
                        AND end_date >= :fromdate
                        AND start_date <= :todate
                ),
                holiday_days AS (
                    SELECT CAST(date AS DATE) AS holiday_date, name
                    FROM public_holidays
                    WHERE date >= :fromdate AND date <= :todate
                )
                SELECT
                    dr.the_date,
                    se.erp_id AS erp_id,
                    se.name AS name,
                    d.title AS designation,
                    g.name AS grade,
                    s.name AS section,
                    att.checkin_time,
                    att.checkout_time,
                    MAX(l.leave_type) AS leave_type,
                    MAX(ow.leave_type) AS official_type,
                    MAX(h.name) AS holiday_name
                FROM date_range dr
                CROSS JOIN section_employees se
                LEFT JOIN sections s ON s.id = se.section_id
                LEFT JOIN designations d ON d.id = se.designation_id
                LEFT JOIN grades g ON g.id = se.grade_id
                LEFT JOIN att
                    ON att.user_id = se.hris_id
                    AND att.att_date = dr.the_date
                LEFT JOIN leave_days l
                    ON l.erp_id = se.erp_id
                    AND dr.the_date BETWEEN l.start_date AND l.end_date
                LEFT JOIN official_days ow
                    ON ow.erp_id = se.erp_id
                    AND dr.the_date BETWEEN ow.start_date AND ow.end_date
                LEFT JOIN holiday_days h
                    ON h.holiday_date = dr.the_date
                GROUP BY
                    dr.the_date,
                    se.id,
                    se.erp_id,
                    se.name,
                    d.title,
                    g.name,
                    s.name,
                    att.checkin_time,
                    att.checkout_time
                ORDER BY
                    s.name,
                    g.name DESC,
                    se.name,
                    dr.the_date
            """)

            rows = session.execute(query, params).fetchall()

            check_in_deadline = time(8, 30)
            check_out_deadline = time(16, 0)
            today = datetime.now().date()

            for row in rows:
                checkin = row.checkin_time
                checkout = row.checkout_time

                late_status = "-"
                early_status = "-"
                if checkin is not None:
                    late_status = "Late" if checkin.time() > check_in_deadline else "On Time"
                if checkout is not None:
                    early_status = "Early" if checkout.time() < check_out_deadline else "On Time"

                # Day status precedence:
                # present > leave > official work > holiday > weekend > future (not reached) > absent
                the_date = row.the_date.date() if isinstance(row.the_date, datetime) else row.the_date
                weekday = the_date.weekday() if the_date else None
                if checkin is not None or checkout is not None:
                    flag, flag_type = "Present", "present"
                elif row.leave_type:
                    flag, flag_type = row.leave_type, "leave"
                elif row.official_type:
                    flag, flag_type = row.official_type, "official"
                elif row.holiday_name:
                    flag, flag_type = row.holiday_name, "holiday"
                elif weekday in (5, 6):
                    flag, flag_type = "Weekend", "weekend"
                elif the_date and the_date > today:
                    # The day hasn't happened yet — no attendance to report.
                    flag, flag_type = "-", "future"
                else:
                    flag, flag_type = "Absent", "absent"

                records.append({
                    "erp_id": row.erp_id,
                    "name": row.name,
                    "designation": row.designation,
                    "grade": row.grade,
                    "section": row.section,
                    "date": row.the_date.strftime("%Y-%m-%d") if row.the_date else None,
                    "checkin_time": checkin.strftime("%Y-%m-%d %H:%M:%S") if checkin is not None else "-",
                    "checkout_time": checkout.strftime("%Y-%m-%d %H:%M:%S") if checkout is not None else "-",
                    "late_status": late_status,
                    "early_status": early_status,
                    "flag": flag,
                    "flag_type": flag_type,
                })

            # Supervising head of each section on the report — the most senior
            # employee it holds (grade_id ranks G-01..G-11 low to high). Ties
            # are ordered by name so the pick is stable between calls.
            heads_query = text(f"""
                SELECT
                    s.id    AS section_id,
                    s.name  AS section_name,
                    e.erp_id,
                    e.name,
                    d.title AS designation,
                    g.name  AS grade
                FROM employees e
                INNER JOIN sections s ON s.id = e.section_id
                LEFT JOIN designations d ON d.id = e.designation_id
                LEFT JOIN grades g ON g.id = e.grade_id
                WHERE e.flag = 1
                    AND e.grade_id = (
                        SELECT MAX(e2.grade_id)
                        FROM employees e2
                        WHERE e2.flag = 1
                            AND e2.section_id = e.section_id
                    )
                    {section_filter}
                ORDER BY s.name, e.name
            """)

            heads = [
                {
                    "section_id": h.section_id,
                    "section": h.section_name,
                    "erp_id": h.erp_id,
                    "name": h.name,
                    "designation": h.designation,
                    "grade": h.grade,
                }
                for h in session.execute(heads_query, params).fetchall()
            ]

            return JsonResponse({"records": records, "heads": heads})

        finally:
            session.close()

    @csrf_exempt
    @require_POST
    def attendance_monthly_summary(request):
        """
        One row per employee for the requested month: the days they were
        present, the days they were absent and the approved leave days they
        took.

        Each (employee, day) of the month falls into exactly one bucket, using
        the same precedence as the section monthly report:
            present > leave > official work > holiday > weekend > absent
        so a day is never counted twice. Days that have not happened yet are
        not counted as absent — for the running month the absent tally only
        covers the days up to today.
        """
        data = json.loads(request.body.decode("utf-8"))
        fromdate = data.get("fromdate")
        todate = data.get("todate")

        if not fromdate or not todate:
            return JsonResponse(
                {"error": "fromdate and todate are required"}, status=400
            )

        session = SessionLocal()
        records = []

        try:
            query = text("""
                WITH date_range AS
                (
                    SELECT CAST(DATEADD(DAY, v.number, :fromdate) AS DATE) AS the_date
                    FROM master..spt_values v
                    WHERE v.type = 'P'
                    AND DATEADD(DAY, v.number, :fromdate) <= :todate
                ),

                -- shift_user_map is the roster both shift screens are built on
                -- (the NCC/RCC split only comes from the SDXP roster API), so
                -- an employee listed here is a shift employee either way.
                shift_users AS
                (
                    SELECT
                        m.ErpID AS erp_id,
                        STRING_AGG(m.Shift_Name, ', ')
                            WITHIN GROUP (ORDER BY m.Shift_Name) AS shift_names
                    FROM (
                        SELECT DISTINCT ErpID, Shift_Name
                        FROM shift_user_map
                    ) m
                    GROUP BY m.ErpID
                ),

                employees_data AS
                (
                    SELECT
                        e.erp_id,
                        e.hris_id,
                        e.name,
                        ISNULL(s.name, '-') AS department,
                        ISNULL(d.title, '-') AS designation,
                        ISNULL(loc.name, '-') AS location,
                        g.name AS grade,
                        CASE WHEN su.erp_id IS NOT NULL THEN 1 ELSE 0 END AS is_shift,
                        ISNULL(su.shift_names, '-') AS shift_names
                    FROM employees e
                    LEFT JOIN sections s
                        ON s.id = e.section_id
                    LEFT JOIN designations d
                        ON d.id = e.designation_id
                    LEFT JOIN locations loc
                        ON loc.id = e.location_id
                    LEFT JOIN grades g
                        ON g.id = e.grade_id
                    LEFT JOIN shift_users su
                        ON su.erp_id = e.erp_id
                    WHERE e.flag = 1
                ),

                attendance_days AS
                (
                    SELECT DISTINCT
                        user_id,
                        CAST(timestamp AS DATE) AS att_date
                    FROM attendance
                    WHERE timestamp >= :fromdate
                    AND timestamp < DATEADD(DAY, 1, :todate)
                ),

                -- Leave and official work are stored as ranges; expand them to
                -- one DISTINCT row per (employee, day) so overlapping requests
                -- cannot multiply an employee's days in the grid below.
                leave_dates AS
                (
                    SELECT DISTINCT
                        l.erp_id,
                        dr.the_date
                    FROM leaves l
                    JOIN date_range dr
                        ON dr.the_date BETWEEN CAST(l.start_date AS DATE)
                                           AND CAST(l.end_date AS DATE)
                    WHERE l.status = 'approved'
                    AND l.end_date >= :fromdate
                    AND l.start_date <= :todate
                ),

                official_dates AS
                (
                    SELECT DISTINCT
                        ow.erp_id,
                        dr.the_date
                    FROM official_work_leaves ow
                    JOIN date_range dr
                        ON dr.the_date BETWEEN CAST(ow.start_date AS DATE)
                                           AND CAST(ow.end_date AS DATE)
                    WHERE ow.status = 'approved'
                    AND ow.end_date >= :fromdate
                    AND ow.start_date <= :todate
                ),

                holiday_dates AS
                (
                    SELECT DISTINCT
                        CAST(date AS DATE) AS holiday_date
                    FROM public_holidays
                    WHERE date >= :fromdate
                    AND date <= :todate
                )

                SELECT
                    ed.erp_id,
                    ed.name,
                    ed.department,
                    ed.designation,
                    ed.location,
                    ed.is_shift,
                    ed.shift_names,

                    SUM(
                        CASE
                            WHEN a.user_id IS NOT NULL
                            THEN 1
                            ELSE 0
                        END
                    ) AS total_present,

                    SUM(
                        CASE
                            WHEN a.user_id IS NOT NULL
                            THEN 0
                            WHEN l.erp_id IS NOT NULL
                            THEN 1
                            ELSE 0
                        END
                    ) AS approved_leaves,

                    SUM(
                        CASE
                            -- Present
                            WHEN a.user_id IS NOT NULL
                            THEN 0

                            -- Approved leave
                            WHEN l.erp_id IS NOT NULL
                            THEN 0

                            -- Official work
                            WHEN ow.erp_id IS NOT NULL
                            THEN 0

                            -- Public holiday
                            WHEN h.holiday_date IS NOT NULL
                            THEN 0

                            -- Saturday
                            WHEN DATEPART(WEEKDAY, dr.the_date) = 7
                            THEN 0

                            -- Sunday
                            WHEN DATEPART(WEEKDAY, dr.the_date) = 1
                            THEN 0

                            -- Day has not happened yet
                            WHEN dr.the_date > CAST(GETDATE() AS DATE)
                            THEN 0

                            ELSE 1
                        END
                    ) AS total_absent

                FROM employees_data ed

                CROSS JOIN date_range dr

                LEFT JOIN attendance_days a
                    ON a.user_id = ed.hris_id
                AND a.att_date = dr.the_date

                LEFT JOIN leave_dates l
                    ON l.erp_id = ed.erp_id
                AND l.the_date = dr.the_date

                LEFT JOIN official_dates ow
                    ON ow.erp_id = ed.erp_id
                AND ow.the_date = dr.the_date

                LEFT JOIN holiday_dates h
                    ON h.holiday_date = dr.the_date

                GROUP BY
                    ed.erp_id,
                    ed.name,
                    ed.department,
                    ed.designation,
                    ed.location,
                    ed.is_shift,
                    ed.shift_names,
                    ed.grade

                ORDER BY
                    ed.department,
                    ed.grade DESC,
                    ed.name
            """)

            rows = session.execute(
                query,
                {
                    "fromdate": fromdate,
                    "todate": todate,
                },
            ).fetchall()

            for row in rows:
                records.append({
                    "erp_id": row.erp_id,
                    "name": row.name,
                    "department": row.department,
                    "designation": row.designation,
                    "location": row.location,
                    "is_shift": bool(row.is_shift),
                    "shift_names": row.shift_names,
                    "total_present": row.total_present,
                    "total_absent": row.total_absent,
                    "approved_leaves": row.approved_leaves,
                })

            return JsonResponse(records, safe=False)

        finally:
            session.close()

    @csrf_exempt
    @require_POST
    def attendance_monthly_employee_days(request):
        """
        The day-by-day detail behind one row of the monthly summary.

        Returns every day of the requested month for a single employee with the
        day's first check-in, last check-out and the bucket it fell into, using
        exactly the same precedence as attendance_monthly_summary
            present > leave > official work > holiday > weekend > absent
        so the counts in the summary and the rows listed here always agree.

        Alongside that, every leave request touching the month is returned with
        its own status — approved, pending or rejected — so a pending request
        can be seen next to the days it would cover.
        """
        data = json.loads(request.body.decode("utf-8"))
        erp_id = data.get("erp_id")
        fromdate = data.get("fromdate")
        todate = data.get("todate")

        if not erp_id or not fromdate or not todate:
            return JsonResponse(
                {"error": "erp_id, fromdate and todate are required"}, status=400
            )

        session = SessionLocal()
        try:
            params = {"erpid": erp_id, "fromdate": fromdate, "todate": todate}

            employee = session.execute(text("""
                SELECT
                    e.erp_id,
                    e.name,
                    ISNULL(s.name, '-') AS department,
                    ISNULL(d.title, '-') AS designation,
                    ISNULL(loc.name, '-') AS location,
                    ISNULL(g.name, '-')  AS grade,
                    ISNULL(su.shift_names, '-') AS shift_names,
                    CASE WHEN su.erp_id IS NOT NULL THEN 1 ELSE 0 END AS is_shift
                FROM employees e
                LEFT JOIN sections s     ON s.id = e.section_id
                LEFT JOIN designations d ON d.id = e.designation_id
                LEFT JOIN locations loc  ON loc.id = e.location_id
                LEFT JOIN grades g       ON g.id = e.grade_id
                LEFT JOIN (
                    SELECT
                        m.ErpID AS erp_id,
                        STRING_AGG(m.Shift_Name, ', ')
                            WITHIN GROUP (ORDER BY m.Shift_Name) AS shift_names
                    FROM (
                        SELECT DISTINCT ErpID, Shift_Name
                        FROM shift_user_map
                    ) m
                    GROUP BY m.ErpID
                ) su ON su.erp_id = e.erp_id
                WHERE e.erp_id = :erpid
            """), {"erpid": erp_id}).first()

            if employee is None:
                return JsonResponse({"error": "employee not found"}, status=404)

            query = text("""
                WITH date_range AS (
                    SELECT CAST(DATEADD(DAY, v.number, :fromdate) AS DATE) AS the_date
                    FROM master..spt_values v
                    WHERE v.type = 'P'
                        AND DATEADD(DAY, v.number, :fromdate) <= :todate
                ),
                att AS (
                    SELECT
                        CAST(a.timestamp AS DATE) AS att_date,
                        MIN(CASE WHEN a.status = 'Checked In' THEN a.timestamp END) AS checkin_time,
                        MAX(CASE WHEN a.status IN ('Checked Out', 'Early Checked Out') THEN a.timestamp END) AS checkout_time,
                        MAX(a.lateintime) AS lateintime,
                        -- The summary counts any punch on a day as present, so
                        -- keep that test here too rather than relying on the
                        -- check-in / check-out statuses being present.
                        COUNT(*) AS punches
                    FROM attendance a
                    WHERE a.timestamp >= :fromdate
                        AND a.timestamp < DATEADD(DAY, 1, :todate)
                        AND a.user_id = (SELECT hris_id FROM employees WHERE erp_id = :erpid)
                    GROUP BY CAST(a.timestamp AS DATE)
                ),
                leave_days AS (
                    SELECT erp_id, leave_type,
                           CAST(start_date AS DATE) AS start_date,
                           CAST(end_date AS DATE) AS end_date
                    FROM leaves
                    WHERE status = 'approved'
                        AND erp_id = :erpid
                        AND end_date >= :fromdate
                        AND start_date <= :todate
                ),
                official_days AS (
                    SELECT erp_id, leave_type,
                           CAST(start_date AS DATE) AS start_date,
                           CAST(end_date AS DATE) AS end_date
                    FROM official_work_leaves
                    WHERE status = 'approved'
                        AND erp_id = :erpid
                        AND end_date >= :fromdate
                        AND start_date <= :todate
                ),
                holiday_days AS (
                    SELECT CAST(date AS DATE) AS holiday_date, name
                    FROM public_holidays
                    WHERE date >= :fromdate AND date <= :todate
                )
                SELECT
                    dr.the_date,
                    MIN(att.checkin_time)   AS checkin_time,
                    MAX(att.checkout_time)  AS checkout_time,
                    MAX(att.lateintime)     AS lateintime,
                    MAX(att.punches)        AS punches,
                    MAX(l.leave_type)       AS leave_type,
                    MAX(ow.leave_type)      AS official_type,
                    MAX(h.name)             AS holiday_name
                FROM date_range dr
                LEFT JOIN att
                    ON att.att_date = dr.the_date
                LEFT JOIN leave_days l
                    ON dr.the_date BETWEEN l.start_date AND l.end_date
                LEFT JOIN official_days ow
                    ON dr.the_date BETWEEN ow.start_date AND ow.end_date
                LEFT JOIN holiday_days h
                    ON h.holiday_date = dr.the_date
                GROUP BY dr.the_date
                ORDER BY dr.the_date
            """)

            rows = session.execute(query, params).fetchall()

            check_in_deadline = time(8, 30)
            check_out_deadline = time(16, 0)
            today = datetime.now().date()

            days = []
            for row in rows:
                checkin = row.checkin_time
                checkout = row.checkout_time
                the_date = (
                    row.the_date.date()
                    if isinstance(row.the_date, datetime)
                    else row.the_date
                )

                late_status = "-"
                early_status = "-"
                if checkin is not None:
                    late_status = (
                        "Late" if checkin.time() > check_in_deadline else "On Time"
                    )
                if checkout is not None:
                    early_status = (
                        "Early" if checkout.time() < check_out_deadline else "On Time"
                    )

                # A day the device recorded at all counts as present, matching
                # the summary's DISTINCT-day attendance bucket.
                if row.punches:
                    status, status_type = "Present", "present"
                elif row.leave_type:
                    status, status_type = row.leave_type, "leave"
                elif row.official_type:
                    status, status_type = row.official_type, "official"
                elif row.holiday_name:
                    status, status_type = row.holiday_name, "holiday"
                elif the_date and the_date.weekday() in (5, 6):
                    status, status_type = "Weekend", "weekend"
                elif the_date and the_date > today:
                    status, status_type = "-", "future"
                else:
                    status, status_type = "Absent", "absent"

                days.append({
                    "date": the_date.strftime("%Y-%m-%d") if the_date else None,
                    "day_name": the_date.strftime("%A") if the_date else "-",
                    "checkin_time": checkin.strftime("%H:%M:%S") if checkin else "-",
                    "checkout_time": checkout.strftime("%H:%M:%S") if checkout else "-",
                    "lateintime": row.lateintime if row.lateintime is not None else "-",
                    "late_status": late_status,
                    "early_status": early_status,
                    "status": status,
                    "status_type": status_type,
                })

            # Days already spoken for by an actual punch — an approved leave day
            # the employee still came in on is reported as present by the
            # summary, so flag it here rather than counting it twice.
            present_dates = {d["date"] for d in days if d["status_type"] == "present"}

            leave_rows = session.execute(text("""
                SELECT
                    l.id,
                    l.leave_type,
                    CAST(l.start_date AS DATE) AS start_date,
                    CAST(l.end_date AS DATE)   AS end_date,
                    l.total_days,
                    l.reason,
                    l.status,
                    l.approved_by,
                    l.created_at
                FROM leaves l
                WHERE l.erp_id = :erpid
                    AND l.end_date >= :fromdate
                    AND l.start_date <= :todate
                ORDER BY l.start_date DESC
            """), params).fetchall()

            month_start = datetime.strptime(fromdate, "%Y-%m-%d").date()
            month_end = datetime.strptime(todate, "%Y-%m-%d").date()

            leaves = []
            for leave in leave_rows:
                start = leave.start_date
                end = leave.end_date
                if isinstance(start, datetime):
                    start = start.date()
                if isinstance(end, datetime):
                    end = end.date()

                # Only the part of the request that falls inside the month is
                # relevant to this report; a leave may span a month boundary.
                span_start = max(start, month_start) if start else month_start
                span_end = min(end, month_end) if end else month_end

                dates = []
                cursor = span_start
                while cursor <= span_end:
                    stamp = cursor.strftime("%Y-%m-%d")
                    dates.append({
                        "date": stamp,
                        "day_name": cursor.strftime("%A"),
                        "weekend": cursor.weekday() in (5, 6),
                        "attended": stamp in present_dates,
                    })
                    cursor += timedelta(days=1)

                status = (leave.status or "pending").lower()
                counted = sum(
                    1 for d in dates
                    if status == "approved" and not d["attended"]
                )

                leaves.append({
                    "id": leave.id,
                    "leave_type": leave.leave_type or "-",
                    "start_date": start.strftime("%Y-%m-%d") if start else "-",
                    "end_date": end.strftime("%Y-%m-%d") if end else "-",
                    "total_days": leave.total_days,
                    "days_in_month": len(dates),
                    "counted_days": counted,
                    "reason": leave.reason or "-",
                    "status": status,
                    "approved_by": leave.approved_by or "-",
                    "applied_on": (
                        leave.created_at.strftime("%Y-%m-%d")
                        if leave.created_at else "-"
                    ),
                    "dates": dates,
                })

            return JsonResponse({
                "employee": {
                    "erp_id": employee.erp_id,
                    "name": employee.name,
                    "department": employee.department,
                    "designation": employee.designation,
                    "location": employee.location,
                    "grade": employee.grade,
                    "is_shift": bool(employee.is_shift),
                    "shift_names": employee.shift_names,
                },
                "days": days,
                "leaves": leaves,
            })

        finally:
            session.close()

    @csrf_exempt
    @require_POST
    def attendance_section(request):
        data = json.loads(request.body.decode("utf-8"))
        section = data.get("section")
        date = data.get("date")

        session = SessionLocal()
        records = []

        try:

            query = text("""
                SELECT
                    e.id AS id,
                    e.erp_id,
                    e.hris_id,
                    e.name,
                    d.title AS designation,
                    g.name AS grade,
                    s.name AS section,
                    a.uid,
                    a.timestamp,
                    a.status,
                    a.lateintime,
                    a.punch

                FROM employees e

                LEFT JOIN sections s
                    ON s.id = e.section_id

                LEFT JOIN designations d
                    ON d.id = e.designation_id

                LEFT JOIN grades g
                    ON g.id = e.grade_id

                LEFT JOIN attendance a
                    ON e.hris_id = a.user_id
                AND CAST(a.timestamp AS DATE)=:date

                WHERE
                    e.flag = 1
                    AND e.section_id = :section

                ORDER BY
                    g.name DESC,
                    e.erp_id
            """)

            rows = session.execute(
                query,
                {
                    "section": section,
                    "date": date
                }
            ).fetchall()

            check_in_deadline = time(8, 30)
            check_out_deadline = time(16, 0)

            attendance_date = datetime.strptime(date, "%Y-%m-%d").date()

            for row in rows:

                flag = "Absent"
                late_status = "-"

                if row.uid is not None:

                    flag = "Present"

                    if row.status == "Checked In":

                        punch_time = row.timestamp.time()

                        if punch_time > check_in_deadline:
                            late_status = "Late"
                        else:
                            late_status = "On Time"

                    elif row.status == "Checked Out":

                        punch_time = row.timestamp.time()

                        if punch_time < check_out_deadline:
                            late_status = "Early Checkout"
                        else:
                            late_status = "On Time"

                    elif row.status == "Early Checked Out":
                        late_status = "Early Checkout"

                else:

                    leave = session.execute(text("""
                        SELECT TOP 1 leave_type
                        FROM leaves
                        WHERE erp_id=:erp_id
                        AND status='approved'
                        AND CAST(start_date AS DATE)<=:att_date
                        AND CAST(end_date AS DATE)>=:att_date
                    """), {
                        "erp_id": row.erp_id,
                        "att_date": attendance_date
                    }).first()

                    official = session.execute(text("""
                        SELECT TOP 1 leave_type
                        FROM official_work_leaves
                        WHERE erp_id=:erp_id
                        AND status='approved'
                        AND CAST(start_date AS DATE)<=:att_date
                        AND CAST(end_date AS DATE)>=:att_date
                    """), {
                        "erp_id": row.erp_id,
                        "att_date": attendance_date
                    }).first()

                    holiday = session.execute(text("""
                        SELECT TOP 1 name
                        FROM public_holidays
                        WHERE CAST(date AS DATE)=:att_date
                    """), {
                        "att_date": attendance_date
                    }).first()

                    weekday = attendance_date.weekday()

                    if leave:
                        flag = leave.leave_type

                    elif official:
                        flag = official.leave_type

                    elif holiday:
                        flag = holiday.name

                    elif weekday == 5:
                        flag = "Saturday"

                    elif weekday == 6:
                        flag = "Sunday"

                    else:
                        flag = "Absent"

                records.append({
                    "id": row.id,
                    "erp_id": row.erp_id,
                    "name": row.name,
                    "designation": row.designation,
                    "grade": row.grade,
                    "section": row.section,
                    "timestamp": "-" if row.timestamp is None else row.timestamp,
                    "late": late_status,
                    "flag": flag,
                    "status": "-" if row.status is None else row.status,
                    "punch": row.punch
                })

            return JsonResponse(records, safe=False)

        finally:
            session.close()
            
    @csrf_exempt
    @require_POST
    def attendance_status(request):
        data = json.loads(request.body.decode('utf-8'))
        section = data.get('section')
        status = data.get('status')
        date = data.get('date')

        session = SessionLocal()
        records = []
        try:
            # Determine which status to filter by
            if status.lower() == 'present':
                # Present: attendance entry exists for the date and section
                query = text("""
                    SELECT
                        e.id AS id,
                        a.uid AS uid,
                        e.erp_id AS erp_id,
                        e.name AS name,
                        g.name AS grade,
                        d.title AS designation,
                        s.name AS section,
                        a.timestamp AS timestamp,
                        a.status AS status,
                        a.lateintime AS lateintime
                    FROM employees e
                    LEFT JOIN sections s ON s.id = e.section_id
                    LEFT JOIN designations d ON d.id = e.designation_id
                    LEFT JOIN grades g ON g.id = e.grade_id
                    LEFT JOIN attendance a ON e.hris_id = a.user_id AND CAST(a.timestamp AS DATE) = :date
                    WHERE s.id = :section
                       AND a.uid IS NOT NULL
                       AND a.status IN ('Checked In', 'Checked Out', 'Early Checked Out') AND e.flag = 1
                    ORDER BY
                       g.name DESC
                """)
            elif status.lower() == 'absent':
                # Absent: no attendance entry for the date and section
                query = text("""
                    SELECT
                        e.id AS id,
                        NULL AS uid,
                        e.erp_id AS erp_id,
                        e.name AS name,
                        d.title AS designation,
                        g.name AS grade,
                        s.name AS section,
                        NULL AS timestamp,
                        NULL AS status,
                        NULL AS lateintime                   
                    FROM employees e
                    LEFT JOIN sections s ON s.id = e.section_id
                    LEFT JOIN designations d ON d.id = e.designation_id
                    LEFT JOIN grades g ON g.id = e.grade_id
                    LEFT JOIN attendance a ON e.hris_id = a.user_id AND CAST(a.timestamp AS DATE) = :date
                    WHERE s.id = :section
                      AND a.uid IS NULL
                      AND e.flag = 1
                    ORDER BY
                        g.name DESC
                """)
            else:
                # Default: show all with attendance entry for the date and section
                query = text("""
                    SELECT
                        e.id AS id,
                        a.uid AS uid,
                        e.erp_id AS erp_id,
                        e.name AS name,
                        d.title AS designation,
                        g.name AS grade,
                        s.name AS section,
                        a.timestamp AS timestamp,
                        a.status AS status,
                        a.lateintime AS lateintime
                    FROM employees e
                    LEFT JOIN sections s ON s.id = e.section_id
                    LEFT JOIN designations d ON d.id = e.designation_id
                    LEFT JOIN grades g ON g.id = e.grade_id
                    LEFT JOIN attendance a ON e.hris_id = a.user_id AND CAST(a.timestamp AS DATE) = :date
                    WHERE s.id = :section
                       AND a.status IN ('Checked In', 'Checked Out', 'Early Checked Out') AND e.flag = 1
                    ORDER BY
                        g.name DESC
                """)
            result = session.execute(
                query, {"section": section, "date": date})
            for row in result:

                records.append({
                    'id': row.id,
                    'erp_id': row.erp_id,
                    'name': row.name,
                    'designation': row.designation,
                    'grade': row.grade,
                    'section': row.section,
                    'timestamp': '-' if row.timestamp is None else row.timestamp,
                 
                    'flag': 'Present' if row.uid is not None else 'Absent',
                    
                })
            return JsonResponse(records, safe=False)
        finally:
            session.close()

    @require_GET
    def getshifts(request):
        session=SessionLocal()
        data=[]
        query=text("""
        SELECT MIN(id) AS id, MIN(Shift_Id) AS shift_id, Shift_Name AS name
FROM dbo.shift_user_map
GROUP BY Shift_Name;

        """)
        results=session.execute(query).fetchall()
        session.close()
        for row in results:
            data.append({
                'id': row.id,
                'shift_id': row.shift_id,
                'name': row.name
            })
        return JsonResponse(data, safe=False)


    @csrf_exempt
    @require_POST
    def shift_details(request):
        # Parse JSON body
        try:
            data = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError:
            print("Invalid JSON format in request body")
            return JsonResponse({"error": "Invalid JSON format"}, status=400)

        shiftid = data.get('shiftid')
        date_str = data.get('date')
        if not shiftid or not date_str:
            print("Missing shiftid or date in request")
            return JsonResponse({"error": "Missing shiftid or date"}, status=400)

        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            print(f"Invalid date format: {date_str}")
            return JsonResponse({"error": "Invalid date format, expected YYYY-MM-DD"}, status=400)

        # Fetch shift details from external API
        url = os.environ.get('SDXP_URL')
        if not url:
            print("SDXP_URL not set in environment variables")
            return JsonResponse({"error": "SDXP_URL not set"}, status=500)

        try:
            response = requests.post(
                f'{url}/ShiftRoster/GetShiftDetails',
                json={"shiftid": shiftid, "date": date_str},
                timeout=5
            )
            response.raise_for_status()
            shift_details = response.json()
            if not shift_details or not isinstance(shift_details, list):
                print("Invalid or empty shift details from API")
                return JsonResponse({"error": "Invalid shift details"}, status=502)
        except requests.RequestException as e:
            print(f"Failed to fetch shift details: {str(e)}")
            return JsonResponse({"error": f"Failed to fetch shift details: {str(e)}"}, status=502)

        # Create mapping of User_Name to Shift_Type and shift times
        shift_type_map = {}
        shift_time_map = {}
        for entry in shift_details:
            user_name = entry.get('User_Name')
            if user_name:
                if user_name not in shift_type_map:
                    shift_type_map[user_name] = entry.get('Shift_Type', '-')
                    shift_time_map[user_name] = {
                        'Start_Time': entry.get('Start_Time'),
                        'End_Time': entry.get('End_Time')
                    }

        session = SessionLocal()
        try:
            # Bulk fetch leaves and holidays
            leaves = {row.erp_id: row.leave_type for row in session.execute(
                text("SELECT erp_id, leave_type FROM leaves WHERE CAST(start_date AS DATE) <= :att_date AND CAST(end_date AS DATE) >= :att_date"),
                {"att_date": date_obj}
            ).fetchall()}
            official_leaves = {row.erp_id: row.leave_type for row in session.execute(
                text("SELECT erp_id, leave_type FROM official_work_leaves WHERE CAST(start_date AS DATE) <= :att_date AND CAST(end_date AS DATE) >= :att_date"),
                {"att_date": date_obj}
            ).fetchall()}
            holiday = session.execute(
                text("SELECT name FROM public_holidays WHERE CAST(date AS DATE) = :att_date"),
                {"att_date": date_obj}
            ).first()
            holiday_name = holiday.name if holiday else None

            # Updated SQL query to match shift_history
            query = text("""
                SELECT 
                    s.Shift_Id,
                    e.erp_id,
                    e.name,
                    s.Sdxp_Username AS user_name,
                    d.title AS title,
                    CAST(a.timestamp AS DATE) AS attendance_date,
                    g.name AS grade,
                    sec.name AS section,
                    s.Shift_Name,
                    MAX(CASE WHEN a.status = 'Checked In' THEN a.timestamp END) AS checkin_time,
                    MAX(CASE WHEN a.status IN ('Checked Out', 'Early Checked Out') THEN a.timestamp END) AS checkout_time,
                    STRING_AGG(a.status, ', ') AS status
                FROM employees e 
                JOIN shift_user_map s ON s.ErpID = e.erp_id
                LEFT JOIN attendance a ON e.hris_id = a.user_id 
                    AND CAST(a.timestamp AS DATE) = :att_date
                JOIN sections sec ON e.section_id = sec.id
                JOIN designations d ON e.designation_id = d.id
                JOIN grades g ON e.grade_id = g.id
                WHERE e.flag = 1 
                    AND s.Shift_Id = :shiftid
                GROUP BY 
                    s.Shift_Id,
                    e.erp_id,
                    e.name,
                    s.Sdxp_Username,
                    d.title,
                    g.name,
                    sec.name,
                    s.Shift_Name,
                    CAST(a.timestamp AS DATE)
                ORDER BY g.name DESC, attendance_date
            """)
            attendance_records = session.execute(
                query, {"shiftid": shiftid, "att_date": date_obj}).fetchall()

            def get_late_status(row, user_name):
                if not row.checkin_time and not row.checkout_time:
                    return '-'
                if user_name not in shift_time_map:
                    print(f"No shift times for user_name: {user_name}")
                    return '-'
                try:
                    shift_times = shift_time_map[user_name]
                    shift_start = shift_times['Start_Time']
                    shift_end = shift_times['End_Time']
                    status_parts = []
                    if row.checkin_time:
                        shift_start_time = (datetime.strptime(
                            shift_start, "%I:%M %p") + timedelta(minutes=30)).time()
                        checkin_time = row.checkin_time.time()
                        if checkin_time <= shift_start_time:
                            status_parts.append('On Time-In')
                        else:
                            status_parts.append('Late In')
                    if row.checkout_time:
                        end_time = datetime.strptime(shift_end, "%I:%M %p").time()
                        checkout_time = row.checkout_time.time()
                        if checkout_time < end_time:
                            status_parts.append('Early Out')
                        else:
                            status_parts.append('On Time-Out')
                    return ', '.join(status_parts) if status_parts else '-'
                except ValueError as e:
                    print(
                        f"Invalid time format for user_name: {user_name}, times: {shift_times}, error={e}")
                    return '-'

            attendance_records = [
                {
                    'shift_id': row.Shift_Id,
                    'erp_id': row.erp_id,
                    'name': row.name,
                    'designation': row.title,
                    'grade': row.grade,
                    'section': row.section,
                    'shiftname': row.Shift_Name,
                    'shifttype': shift_type_map.get(row.user_name, '-'),
                    'checkin_time': row.checkin_time.strftime("%Y-%m-%d %H:%M:%S") if row.checkin_time else None,
                    'checkout_time': row.checkout_time.strftime("%Y-%m-%d %H:%M:%S") if row.checkout_time else None,
                    'status': '-' if row.status is None else row.status,
                    'timestamp': row.attendance_date.strftime("%Y-%m-%d") if row.attendance_date else None,
                    'lateintime': get_late_status(row, row.user_name),
                    'flag': (
                        'Present' if row.checkin_time or row.checkout_time
                        else leaves.get(row.erp_id) or
                        official_leaves.get(row.erp_id) or
                        holiday_name or 'Absent'
                    )
                } for row in attendance_records
            ]
            return JsonResponse({'attendance': attendance_records}, safe=False, status=200)
        except Exception as e:
            print(f"Database error occurred: {str(e)}")
            return JsonResponse({"error": f"Database error occurred: {str(e)}"}, status=500)
        finally:
            session.close()
      
    @csrf_exempt
    @require_POST
    def shift_history(request):
        """
        Retrieve shift history and attendance details for a given shift and date range.
        
        Args:
            request: HTTP POST request with JSON body containing:
                - shiftid (str): ID of the shift
                - fromdate (str): Start date in YYYY-MM-DD format
                - todate (str): End date in YYYY-MM-DD format
        
        Returns:
            JsonResponse: Attendance records with details like check-in/out times, status, shifttype, and flags.
        """
        try:
            data = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError:
            print("Invalid JSON format in request body")
            return JsonResponse({"error": "Invalid JSON format"}, status=400)

        shiftid = data.get('shiftid')
        fromdate_str = data.get('fromdate')
        todate_str = data.get('todate')

        if not all([shiftid, fromdate_str, todate_str]):
            print("Missing required fields: shiftid, fromdate, todate")
            return JsonResponse({"error": "Missing required fields: shiftid, fromdate, todate"}, status=400)

        try:
            from_date_obj = datetime.strptime(fromdate_str, "%Y-%m-%d").date()
            to_date_obj = datetime.strptime(todate_str, "%Y-%m-%d").date()
        except ValueError:
            print(
                f"Invalid date format: fromdate={fromdate_str}, todate={todate_str}")
            return JsonResponse({"error": "Invalid date format. Use YYYY-MM-DD"}, status=400)

        url = os.environ.get('SDXP_URL')
        if not url:
            print("SDXP_URL not set in environment variables")
            return JsonResponse({"error": "SDXP_URL not set"}, status=500)

        # Fetch shift details
        try:
            response = requests.post(
                f'{url}/ShiftRoster/ShiftDetailed',
                json={"shiftid": shiftid, "fromdate": fromdate_str,
                    "todate": todate_str},
                timeout=5
            )
            response.raise_for_status()
            shift_details = response.json()
            if not shift_details or not isinstance(shift_details, list):
                print("Invalid or empty shift details from API")
                return JsonResponse({"error": "Invalid shift details from API"}, status=502)
        except requests.RequestException as e:
            print(f"Failed to fetch shift details: {str(e)}")
            return JsonResponse({"error": f"Failed to fetch shift details: {str(e)}"}, status=502)

        # Create mapping of User_Name to Shift_Type and shift times
        shift_type_map = {}
        shift_time_map = {}
        for entry in shift_details:
            user_name = entry.get('User_Name')
            if user_name:
                # Prioritize first occurrence (or adjust for RCC/NCC priority if needed)
                if user_name not in shift_type_map:
                    shift_type_map[user_name] = entry.get('Shift_Type', '-')
                    shift_time_map[user_name] = {
                        'Start_Time': entry.get('Start_Time', ''),
                        'End_Time': entry.get('End_Time', '')
                    }

        session = SessionLocal()
        try:
            # Bulk fetch leaves and holidays
            leaves = {row.erp_id: row.leave_type for row in session.execute(
                text("SELECT erp_id, leave_type FROM leaves WHERE CAST(start_date AS DATE) <= :todate AND CAST(end_date AS DATE) >= :fromdate"),
                {"fromdate": from_date_obj, "todate": to_date_obj}
            ).fetchall()}
            official_leaves = {row.erp_id: row.leave_type for row in session.execute(
                text("SELECT erp_id, leave_type FROM official_work_leaves WHERE CAST(start_date AS DATE) <= :todate AND CAST(end_date AS DATE) >= :fromdate"),
                {"fromdate": from_date_obj, "todate": to_date_obj}
            ).fetchall()}
            holidays = {row.date: row.name for row in session.execute(
                text("SELECT CAST(date AS DATE) AS date, name FROM public_holidays WHERE CAST(date AS DATE) BETWEEN :fromdate AND :todate"),
                {"fromdate": from_date_obj, "todate": to_date_obj}
            ).fetchall()}

            # Main query with s.Sdxp_Username for shifttype
            query = text("""
                SELECT 
                    s.Shift_Id,
                    e.erp_id,
                    e.name,
                    s.Sdxp_Username AS user_name,
                    d.title AS title,
                    CAST(a.timestamp AS DATE) AS attendance_date,
                    g.name AS grade,
                    sec.name AS section,
                    s.Shift_Name,
                    MAX(CASE WHEN a.status = 'Checked In' THEN a.timestamp END) AS checkin_time,
                    MAX(CASE WHEN a.status IN ('Checked Out', 'Early Checked Out') THEN a.timestamp END) AS checkout_time,
                    STRING_AGG(a.status, ', ') AS status
                FROM employees e 
                JOIN shift_user_map s ON s.ErpID = e.erp_id
                LEFT JOIN attendance a ON e.hris_id = a.user_id 
                    AND CAST(a.timestamp AS DATE) BETWEEN :fromdate AND :todate
                JOIN sections sec ON e.section_id = sec.id
                JOIN designations d ON e.designation_id = d.id
                JOIN grades g ON e.grade_id = g.id
                WHERE e.flag = 1 
                    AND s.Shift_Id = :shiftid
                GROUP BY 
                    s.Shift_Id,
                    e.erp_id,
                    e.name,
                    s.Sdxp_Username,
                    d.title,
                    g.name,
                    sec.name,
                    s.Shift_Name,
                    CAST(a.timestamp AS DATE)
                ORDER BY g.name DESC, attendance_date
            """)
            attendance_records = session.execute(
                query, {"shiftid": shiftid,
                        "fromdate": from_date_obj, "todate": to_date_obj}
            ).fetchall()

            def get_late_status(row, user_name):
                if not row.checkin_time and not row.checkout_time:
                    return '-'
                if user_name not in shift_time_map:
                    print(f"No shift times for user_name: {user_name}")
                    return '-'
                try:
                    shift_times = shift_time_map[user_name]
                    shift_start = shift_times['Start_Time']
                    shift_end = shift_times['End_Time']
                    if not shift_start or not shift_end:
                        print(
                            f"Missing Start_Time or End_Time for user_name: {user_name}")
                        return '-'
                    status_parts = []
                    if row.checkin_time:
                        shift_start_time = (datetime.strptime(
                            shift_start, "%I:%M %p") + timedelta(minutes=30)).time()
                        checkin_time = row.checkin_time.time()
                        if checkin_time <= shift_start_time:
                            status_parts.append('On Time-In')
                        else:
                            status_parts.append('Late In')
                    if row.checkout_time:
                        end_time = datetime.strptime(shift_end, "%I:%M %p").time()
                        checkout_time = row.checkout_time.time()
                        if checkout_time < end_time:
                            status_parts.append('Early Out')
                        else:
                            status_parts.append('On Time-Out')
                    return ', '.join(status_parts) if status_parts else '-'
                except ValueError as e:
                    print(
                        f"Invalid time format for user_name: {user_name}, times: {shift_times}, error={e}")
                    return '-'

            attendance_records = [
                {
                    'shift_id': row.Shift_Id,
                    'erp_id': row.erp_id,
                    'name': row.name,
                    'designation': row.title,
                    'grade': row.grade,
                    'section': row.section,
                    'shiftname': row.Shift_Name,
                    'shifttype': shift_type_map.get(row.user_name, '-'),
                    'checkin_time': row.checkin_time.strftime("%Y-%m-%d %H:%M:%S") if row.checkin_time else None,
                    'checkout_time': row.checkout_time.strftime("%Y-%m-%d %H:%M:%S") if row.checkout_time else None,
                    'status': '-' if row.status is None else row.status,
                    'timestamp': row.attendance_date.strftime("%Y-%m-%d") if row.attendance_date else None,
                    'lateintime': get_late_status(row, row.user_name),
                    'flag': (
                        'Present' if row.checkin_time or row.checkout_time
                        else leaves.get(row.erp_id) or
                        official_leaves.get(row.erp_id) or
                        holidays.get(row.attendance_date,
                                    'Absent') if row.attendance_date else 'Absent'
                    )
                } for row in attendance_records
            ]
            # Print shift type lookups for debugging
            for record in attendance_records:
                print(
                    f"Shift type lookup: user_name={record['name']}, shifttype={record['shifttype']}")
            return JsonResponse({'attendance': attendance_records}, safe=False, status=200)
        except Exception as e:
            print(f"Database query failed: {str(e)}")
            return JsonResponse({"error": f"Database query failed: {str(e)}"}, status=500)
        finally:
            session.close()
    
    @csrf_exempt
    @require_POST
    def current_attendance(request):
        # Your logic for handling current attendance
        try:
            request_data = json.loads(request.body.decode('utf-8'))
        except Exception as e:
            return JsonResponse({"error": "Invalid JSON format"}, status=400)
        empid = request_data.get("empid")
        date = request_data.get("date")
        if not empid or not date:
            return JsonResponse({"error": "empid and date are required"}, status=400)

        # Fetch current attendance data from the database
        session = SessionLocal()
        try:
            query = text("""
                SELECT 
                    MIN(CASE WHEN status = 'Checked In' THEN timestamp END) AS checkin_time,
                    MAX(CASE WHEN status IN ('Checked Out', 'Early Checked Out') THEN timestamp END) AS checkout_time,
                    MIN(id) AS id,
                    MIN(uid) AS uid,
                    user_id,
                    MIN(punch) AS punch,
                    MIN(lateintime) AS lateintime
                FROM [dbo].[attendance]
                WHERE user_id = :empid 
                AND CAST(timestamp AS DATE) = :date
                GROUP BY user_id
            """)
            result = session.execute(query, {"empid": empid, "date": date})
            attendance = result.fetchall()
            # Serialize attendance rows to dicts
            attendance_list = [
                {
                    "id": row.id,
                    "uid": row.uid,
                    "user_id": row.user_id,
                    "checkin_time": row.checkin_time.isoformat() if row.checkin_time else None,
                    "checkout_time": row.checkout_time.isoformat() if row.checkout_time else None,
                    "status": (
                        "Present" if row.checkin_time or row.checkout_time else "Absent"
                    ),
                    "punch": row.punch,
                    "lateintime": row.lateintime
                }
                for row in attendance
            ]
            return JsonResponse({"attendance": attendance_list}, status=200)
        except Exception as e:
            return JsonResponse({"error": "Attendance not found"}, status=404)
        finally:
            session.close()

    @require_GET
    def my_attendance_today(request):
        """
        Today's attendance snapshot for the currently logged-in user, resolved
        by erp_id. Returns first check-in, last check-out, the late / early
        assessment against the standard 08:30 / 16:00 deadlines, and the day's
        status (present / leave / official work / holiday / weekend / absent),
        following the same precedence used elsewhere in the attendance module.
        """
        erp_id = request.GET.get("erp_id")
        if not erp_id:
            return JsonResponse({"error": "erp_id is required"}, status=400)

        session = SessionLocal()
        try:
            employee = session.execute(text("""
                SELECT
                    e.erp_id,
                    e.hris_id,
                    e.name,
                    d.title AS designation,
                    g.name AS grade,
                    s.name AS section
                FROM employees e
                LEFT JOIN sections s ON s.id = e.section_id
                LEFT JOIN designations d ON d.id = e.designation_id
                LEFT JOIN grades g ON g.id = e.grade_id
                WHERE e.erp_id = :erp_id AND e.flag = 1
            """), {"erp_id": erp_id}).first()

            if not employee:
                return JsonResponse({"error": "Employee not found"}, status=404)

            today = datetime.now().date()

            att = session.execute(text("""
                SELECT
                    MIN(CASE WHEN status = 'Checked In' THEN timestamp END) AS checkin_time,
                    MAX(CASE WHEN status IN ('Checked Out', 'Early Checked Out') THEN timestamp END) AS checkout_time
                FROM attendance
                WHERE user_id = :hris_id
                    AND CAST(timestamp AS DATE) = :today
            """), {"hris_id": employee.hris_id, "today": today}).first()

            checkin = att.checkin_time if att else None
            checkout = att.checkout_time if att else None

            check_in_deadline = time(8, 30)
            check_out_deadline = time(16, 0)

            late_status = "-"
            early_status = "-"
            if checkin is not None:
                late_status = "Late" if checkin.time() > check_in_deadline else "On Time"
            if checkout is not None:
                early_status = "Early" if checkout.time() < check_out_deadline else "On Time"

            # Day-status precedence: present > leave > official work > holiday > weekend > absent
            if checkin is not None or checkout is not None:
                flag, flag_type = "Present", "present"
            else:
                leave = session.execute(text("""
                    SELECT TOP 1 leave_type FROM leaves
                    WHERE erp_id = :erp_id AND status = 'approved'
                    AND CAST(start_date AS DATE) <= :today AND CAST(end_date AS DATE) >= :today
                """), {"erp_id": employee.erp_id, "today": today}).first()

                official = session.execute(text("""
                    SELECT TOP 1 leave_type FROM official_work_leaves
                    WHERE erp_id = :erp_id AND status = 'approved'
                    AND CAST(start_date AS DATE) <= :today AND CAST(end_date AS DATE) >= :today
                """), {"erp_id": employee.erp_id, "today": today}).first()

                holiday = session.execute(text("""
                    SELECT TOP 1 name FROM public_holidays
                    WHERE CAST(date AS DATE) = :today
                """), {"today": today}).first()

                if leave:
                    flag, flag_type = leave.leave_type, "leave"
                elif official:
                    flag, flag_type = official.leave_type, "official"
                elif holiday:
                    flag, flag_type = holiday.name, "holiday"
                elif today.weekday() in (5, 6):
                    flag, flag_type = "Weekend", "weekend"
                else:
                    flag, flag_type = "Absent", "absent"

            return JsonResponse({
                "erp_id": employee.erp_id,
                "name": employee.name,
                "designation": employee.designation,
                "grade": employee.grade,
                "section": employee.section,
                "date": today.isoformat(),
                "checkin_time": checkin.isoformat() if checkin is not None else None,
                "checkout_time": checkout.isoformat() if checkout is not None else None,
                "late_status": late_status,
                "early_status": early_status,
                "flag": flag,
                "flag_type": flag_type,
            }, status=200)

        finally:
            session.close()

    @csrf_exempt
    @require_POST
    def shift_add(request):
        try:
            request_data = json.loads(request.body.decode('utf-8'))
        except Exception:
            return JsonResponse({"error": "Invalid JSON format"}, status=400)
        empid = request_data.get("employeeId")
        date_str = request_data.get("date")
        check_in_str = request_data.get("checkIn")
        check_out_str = request_data.get("checkOut")
        if not empid or not date_str or not check_in_str or not check_out_str:
            return JsonResponse({"error": "All fields are required"}, status=400)

        try:
            # Parse date and time, combine to datetime
            # Accepts check_in/check_out as "HH:MM" or "HH:MM:SS"
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return JsonResponse({"error": "Date must be in YYYY-MM-DD format"}, status=400)
            try:
                check_in_time = datetime.strptime(check_in_str, "%H:%M").time()
            except ValueError:
                try:
                    check_in_time = datetime.strptime(check_in_str, "%H:%M:%S").time()
                except ValueError:
                    return JsonResponse({"error": "CheckIn time must be in HH:MM or HH:MM:SS format"}, status=400)
            try:
                check_out_time = datetime.strptime(check_out_str, "%H:%M").time()
            except ValueError:
                try:
                    check_out_time = datetime.strptime(check_out_str, "%H:%M:%S").time()
                except ValueError:
                    return JsonResponse({"error": "CheckOut time must be in HH:MM or HH:MM:SS format"}, status=400)

            check_in_dt = datetime.combine(date_obj, check_in_time)
            check_out_dt = datetime.combine(date_obj, check_out_time)

            uid_list = Attendance.objects.all().values_list('uid', flat=True)
            unique_uid = AttendanceView.get_random_uid(uid_list)
            new_shift = Attendance.objects.create(
                uid=unique_uid,
                user_id=empid,
                timestamp=check_in_dt,
                status='Checked In',
                punch=1,
                lateintime=''
            )
            new_shift_out = Attendance.objects.create(
                uid=unique_uid,
                user_id=empid,
                timestamp=check_out_dt,
                status='Checked Out',
                punch=1,
                lateintime=''
            )
            return JsonResponse({"message": "Shift added successfully"}, status=201)
        except Exception as e:
            print(f"Error adding shift: {e}")
            return JsonResponse({"error": f"Failed to add shift {e}"}, status=500)
    
    @csrf_exempt
    @require_POST
    def shift_update(request):
        try:
            request_data = json.loads(request.body.decode('utf-8'))
        except Exception:
            return JsonResponse({"error": "Invalid JSON format"}, status=400)
        empid = request_data.get("employeeId")
        date_str = request_data.get("date")
        check_in_str = request_data.get("checkIn")
        check_out_str = request_data.get("checkOut")
        if not empid or not date_str or not check_in_str or not check_out_str:
            return JsonResponse({"error": "All fields are required"}, status=400)

        try:
            # Parse date and time, combine to datetime
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return JsonResponse({"error": "Date must be in YYYY-MM-DD format"}, status=400)
            try:
                check_in_time = datetime.strptime(check_in_str, "%H:%M").time()
            except ValueError:
                try:
                    check_in_time = datetime.strptime(check_in_str, "%H:%M:%S").time()
                except ValueError:
                    return JsonResponse({"error": "CheckIn time must be in HH:MM or HH:MM:SS format"}, status=400)
            try:
                check_out_time = datetime.strptime(check_out_str, "%H:%M").time()
            except ValueError:
                try:
                    check_out_time = datetime.strptime(check_out_str, "%H:%M:%S").time()
                except ValueError:
                    return JsonResponse({"error": "CheckOut time must be in HH:MM or HH:MM:SS format"}, status=400)

            check_in_dt = datetime.combine(date_obj, check_in_time)
            check_out_dt = datetime.combine(date_obj, check_out_time)

            # Update Checked In record if exists, else create
            checkin_qs = Attendance.objects.filter(
                user_id=empid,
                status='Checked In',
                timestamp__date=date_obj
            )
            if checkin_qs.exists():
                checkin_qs.update(
                    timestamp=check_in_dt,
                    punch=1,
                    lateintime=''
                )
            else:
                uid_list = Attendance.objects.all().values_list('uid', flat=True)
                unique_uid = AttendanceView.get_random_uid(uid_list)
                Attendance.objects.create(
                    uid=unique_uid,
                    user_id=empid,
                    timestamp=check_in_dt,
                    status='Checked In',
                    punch=1,
                    lateintime=''
                )

            # Update Checked Out record if exists, else create
            checkout_qs = Attendance.objects.filter(
                user_id=empid,
                status='Checked Out',
                timestamp__date=date_obj
            )
            if checkout_qs.exists():
                checkout_qs.update(
                    timestamp=check_out_dt,
                    punch=1,
                    lateintime=''
                )
            else:
                uid_list = Attendance.objects.all().values_list('uid', flat=True)
                unique_uid = AttendanceView.get_random_uid(uid_list)
                Attendance.objects.create(
                    uid=unique_uid,
                    user_id=empid,
                    timestamp=check_out_dt,
                    status='Checked Out',
                    punch=1,
                    lateintime=''
                )

            return JsonResponse({"message": "Shift updated successfully"}, status=200)
        except Exception as e:
            print(f"Error updating shift: {e}")
            return JsonResponse({"error": f"Failed to update shift {e}"}, status=500)

    @staticmethod
    def get_random_uid(uid_list):
        if not uid_list:
            return 1
        return max(uid_list) + 1