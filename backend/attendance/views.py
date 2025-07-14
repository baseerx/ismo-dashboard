from django.shortcuts import render
from .models import Attendance  # Assuming you have an Attendance model defined
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from datetime import date, datetime
from sqlalchemy import text
from django.views.decorators.csrf import csrf_exempt
import json
# Assuming you have a SessionLocal defined for database access
from db import SessionLocal
# Create your views here.
from leaves.models import LeaveModel
from holidays.models import Holiday


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
                    a.lateintime AS lateintime
                FROM employees e
                LEFT JOIN sections s ON s.id = e.section_id
                LEFT JOIN designations d ON d.id = e.designation_id
                LEFT JOIN attendance a 
                    ON e.hris_id = a.user_id 
                    AND CAST(a.timestamp AS DATE) = :today
                ORDER BY 
                    a.timestamp DESC,
                    CASE a.status
                        WHEN 'Checked In' THEN 0
                        WHEN 'Checked Out' THEN 1
                        ELSE 2
                    END;
            """)
            result = session.execute(query, {"today": today}).fetchall()
            for row in result:
                flag = 'Absent'
                if row.uid is not None:
                    flag = 'Present'
                else:
                    
                    # Check leave
                    leave_result = session.execute(text("""
                        SELECT leave_type FROM leaves
                        WHERE erp_id = :erp_id
                        AND CAST(start_date AS DATE) <= CAST(:att_date AS DATE)
                        AND CAST(end_date AS DATE) >= CAST(:att_date AS DATE)
                    """), {"erp_id": row.erp_id, "att_date": today}).first()
                    
                    if leave_result:
                        flag = leave_result.leave_type
                    else:
                        # Check holiday
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
                    'uid': row.uid,
                    'user_id': row.user_id,
                    'timestamp': '-' if row.timestamp is None else row.timestamp,
                    'late': '-' if row.uid is None else row.lateintime,
                    'status': '-' if row.status is None else row.status,
                    'flag': flag
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
                    a.uid AS uid,
                    e.hris_id AS user_id,
                    a.timestamp AS timestamp,
                    a.status AS status,
                    a.lateintime AS lateintime
                 
                FROM employees e
                LEFT JOIN sections s ON s.id = e.section_id
                LEFT JOIN designations d ON d.id = e.designation_id
                LEFT JOIN attendance a ON e.hris_id = a.user_id 
                    AND CAST(a.timestamp AS DATE) = :today
                WHERE e.section_id = (SELECT id FROM sections WHERE name = :section_name)
                ORDER BY a.timestamp desc,
                         CASE a.status
                             WHEN 'Checked In' THEN 0
                             WHEN 'Checked Out' THEN 1
                             ELSE 2
                         END
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
                if row.uid is not None:
                    flag = 'Present'
                else:
                    if leave_result:
                        flag = leave_result.leave_type
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
                    'uid': row.uid,
                    'user_id': row.user_id,
                    'timestamp': '-' if row.timestamp is None else row.timestamp,
                    'late': '-' if row.uid is None else row.lateintime,
                    'status': '-' if row.status is None else row.status,
                    'flag': flag                })
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
                LEFT JOIN attendance a 
                    ON e.hris_id = a.user_id 
                    AND CAST(a.timestamp AS DATE) = dr.the_date
                WHERE e.erp_id = :erpid
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
            flag='Absent'
            for row in rows:
                leave_result = session.execute(text("""
                        SELECT leave_type FROM leaves
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
                    else:
                        # Check for holiday on that date
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
                    'section': row.section,
                    'uid': row.uid,
                    'user_id': row.user_id,
                    'timestamp': row.the_date if row.timestamp is None else row.timestamp,
                    'late':  row.lateintime,
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
                LEFT JOIN attendance a 
                    ON e.hris_id = a.user_id 
                    AND CAST(a.timestamp AS DATE) = dr.the_date
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
                query, {"fromdate": fromdate, "todate": todate})
            rows = result.fetchall()
            for row in rows:
                flag = 'Absent'
                leave_result = session.execute(text("""
                        SELECT leave_type FROM leaves
                        WHERE erp_id = :erp_id
                        AND CAST(start_date AS DATE) <= CAST(:att_date AS DATE)
                        AND CAST(end_date AS DATE) >= CAST(:att_date AS DATE)
                    """), {"erp_id": row.erp_id, "att_date": row.the_date}).first()
                
                if row.uid is not None:
                    flag = 'Present'
                elif row.the_date:
                    if leave_result:
                        flag = leave_result.leave_type
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
                    'section': row.section,
                    'uid': row.uid,
                    'user_id': row.user_id,
                    'timestamp': row.the_date if row.timestamp is None else row.timestamp,
                    'late': row.lateintime,
                    'flag': flag,
                    'status': '-' if row.status is None else row.status,
                    'punch': row.punch
                })
            return JsonResponse(records, safe=False)
        finally:
            session.close()

    @csrf_exempt
    @require_POST
    def attendance_section(request):
        data = json.loads(request.body.decode('utf-8'))
        section = data.get('section')
        date = data.get('date')

        session = SessionLocal()
        records = []
        try:
            query = text("""
                SELECT
                    e.id AS id,
                    a.uid AS uid,
                    e.erp_id AS erp_id,
                    e.name AS name,
                    d.title AS designation,
                    s.name AS section,
                    a.timestamp AS timestamp,
                    a.status AS status,
                    a.lateintime AS lateintime,
                    a.punch AS punch
                FROM employees e
                LEFT JOIN sections s ON s.id = e.section_id
                LEFT JOIN designations d ON d.id = e.designation_id
                LEFT JOIN attendance a ON e.hris_id = a.user_id AND CAST(a.timestamp AS DATE) = :date
                WHERE s.id = :section
                   AND a.status IN ('Checked In', 'Checked Out', 'Early Checked Out')
                ORDER BY
                    e.name,
                    CAST(a.timestamp AS DATE),
                    CASE 
                        WHEN a.status = 'Checked In' THEN 0
                        WHEN a.status = 'Early Checked Out' THEN 1
                        WHEN a.status = 'Checked Out' THEN 2
                        ELSE 3
                    END,
                    a.timestamp;
            """)
            result = session.execute(
                query, {"section": section, "date": date})
            for row in result:

                records.append({
                    'id': row.id,
                    'erp_id': row.erp_id,
                    'name': row.name,
                    'designation': row.designation,
                    'section': row.section,
                    'timestamp': '-' if row.timestamp is None else row.timestamp,
                    'late': '-' if row.timestamp is None else row.lateintime,
                    'flag': 'Present' if row.uid is not None else 'Absent',
                    'status': '-' if row.status is None else row.status,
                    'punch': row.punch
                })
            return JsonResponse(records, safe=False)
        finally:
            session.close()
