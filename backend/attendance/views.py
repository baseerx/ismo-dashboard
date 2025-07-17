from django.shortcuts import render
from .models import Attendance  # Assuming you have an Attendance model defined
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from datetime import date, datetime,time
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
                ORDER BY 
                    g.name DESC
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
                    official_work = session.execute(text("""
                                        SELECT leave_type FROM official_work_leaves
                                        WHERE erp_id = :erp_id
                                        AND CAST(start_date AS DATE) <= CAST(:att_date AS DATE)
                                        AND CAST(end_date AS DATE) >= CAST(:att_date AS DATE)
                                    """), {"erp_id": row.erp_id, "att_date": today}).first()

                    if leave_result:
                        flag = leave_result.leave_type
                    elif official_work:
                        flag = official_work.leave_type
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
                    'grade': row.grade,
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
                         g.name as grade,
                    a.uid AS uid,
                    e.hris_id AS user_id,
                    a.timestamp AS timestamp,
                    a.status AS status,
                    a.lateintime AS lateintime
                 
                FROM employees e
                LEFT JOIN sections s ON s.id = e.section_id
                LEFT JOIN designations d ON d.id = e.designation_id
                         LEFT JOIN grades g ON g.id = e.grade_id
                LEFT JOIN attendance a ON e.hris_id = a.user_id 
                    AND CAST(a.timestamp AS DATE) = :today
                WHERE e.section_id = (SELECT id FROM sections WHERE name = :section_name) and e.flag = 1
                ORDER BY g.name desc
            """)

            result = session.execute(
                query, {"today": today, "section_name": row.name}).fetchall()
            records = []
            for row in result:
                check_in_deadline = time(9, 0)
                check_out_deadline = time(14, 30)
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
                if row.uid is not None:
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
                    'uid': row.uid,
                    'user_id': row.user_id,
                    'timestamp': '-' if row.timestamp is None else row.timestamp,
                    'late': '-' if flag == 'Absent' else late_status,
                    'status': '-' if row.status is None else row.status,
                    'flag': flag})
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
                check_in_deadline=time(9,0)
                check_out_deadline=time(14,30)
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
                check_in_deadline = time(9, 0)
                check_out_deadline = time(14, 30)
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
                SELECT
                            CAST(a.timestamp AS DATE) AS the_date,
                    e.erp_id AS erp_id,
                    e.name AS name,
                    d.title AS designation,
                    g.name AS grade,
                    s.name AS section,
                    MAX(CASE WHEN a.status = 'Checked In' THEN a.timestamp END) AS checkin_time,
                    MAX(CASE WHEN a.status IN ('Checked Out', 'Early Checked Out') THEN a.timestamp END) AS checkout_time
                FROM attendance a
                JOIN employees e ON e.hris_id = a.user_id
                LEFT JOIN sections s ON s.id = e.section_id
                LEFT JOIN designations d ON d.id = e.designation_id
                LEFT JOIN grades g ON g.id = e.grade_id
                WHERE e.flag = 1
                  AND CAST(a.timestamp AS DATE) BETWEEN :fromdate AND :todate
                GROUP BY 
                    CAST(a.timestamp AS DATE),
                    e.id,
                    e.erp_id,
                    e.name,
                    d.title,
                    g.name,
                    s.name,
                    e.hris_id
                ORDER BY g.name DESC
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
                official_work = session.execute(text("""
                                        SELECT leave_type FROM official_work_leaves
                                        WHERE erp_id = :erp_id
                                        AND CAST(start_date AS DATE) <= CAST(:att_date AS DATE)
                                        AND CAST(end_date AS DATE) >= CAST(:att_date AS DATE)
                                    """), {"erp_id": row.erp_id, "att_date": row.the_date}).first()

                if row.the_date is not None:
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
                    'erp_id': row.erp_id,
                    'name': row.name,
                    'designation': row.designation,
                    'grade': row.grade,
                    'section': row.section,
                    'checkout_time': row.checkout_time if row.checkout_time is not None else '-',
                    'checkin_time': row.checkin_time if row.checkin_time is not None else '-',
                    'timestamp': row.the_date,
                    'late': '-' if flag=='Absent' else flag, 
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
                    g.name AS grade,
                    s.name AS section,
                    a.timestamp AS timestamp,
                    a.status AS status,
                    a.lateintime AS lateintime,
                    a.punch AS punch
                FROM employees e
                LEFT JOIN sections s ON s.id = e.section_id
                LEFT JOIN designations d ON d.id = e.designation_id
                LEFT JOIN grades g ON g.id = e.grade_id
                LEFT JOIN attendance a ON e.hris_id = a.user_id AND CAST(a.timestamp AS DATE) = :date
                WHERE s.id = :section
                   AND a.status IN ('Checked In', 'Checked Out', 'Early Checked Out') AND e.flag = 1
                ORDER BY g.name DESC
            """)
            result = session.execute(
                query, {"section": section, "date": date})
            for row in result:
                check_in_deadline = time(9, 0)
                check_out_deadline = time(14, 30)
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
                    
                records.append({
                    'id': row.id,
                    'erp_id': row.erp_id,
                    'name': row.name,
                    'designation': row.designation,
                    'grade': row.grade,
                    'section': row.section,
                    'timestamp': '-' if row.timestamp is None else row.timestamp,
                    'late': late_status,
                    'flag': 'Present' if row.uid is not None else 'Absent',
                    'status': '-' if row.status is None else row.status,
                    'punch': row.punch
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
