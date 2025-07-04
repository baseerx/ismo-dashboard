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
                    a.lateintime AS lateintime,
                    a.punch AS punch
                FROM employees e
                LEFT JOIN sections s ON s.id = e.section_id
                LEFT JOIN designations d ON d.id = e.designation_id
                LEFT JOIN attendance a ON e.hris_id = a.user_id 
                WHERE CAST(a.timestamp AS DATE) = :today
                ORDER BY a.timestamp desc,
                         CASE a.status
                             WHEN 'Checked In' THEN 0
                             WHEN 'Checked Out' THEN 1
                             ELSE 2
                         END
            """)
            result = session.execute(query, {"today": today})
            for row in result:

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
                    'flag': 'Present' if row.uid is not None else 'Absent',
                    'punch': row.punch
                })
            return JsonResponse(records, safe=False)
        finally:
            session.close()
            
    @csrf_exempt
    @require_POST
    def attendance_individual(request):
        data=json.loads(request.body)
        erpid = data.get('erpid')
        if not erpid:
            return JsonResponse({"error": "erpid is required"}, status=400)
        
        fromdate = data.get('fromdate')
        todate = data.get('todate')
        
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
                    a.lateintime AS lateintime,
                    a.punch AS punch
                FROM employees e
                LEFT JOIN sections s ON s.id = e.section_id
                LEFT JOIN designations d ON d.id = e.designation_id
                LEFT JOIN attendance a ON e.hris_id = a.user_id AND CAST(a.timestamp AS DATE) BETWEEN :fromdate AND :todate
                WHERE e.erp_id = :erpid
                ORDER BY e.id, 
                         CASE 
                             WHEN a.status = 'Checked In' THEN 0
                             WHEN a.status = 'Checked Out' THEN 1
                             ELSE 2
                         END,
                         a.timestamp
            """)
            result = session.execute(query, {"fromdate": fromdate, "todate": todate, "erpid": erpid})
            for row in result:

                records.append({
                    'id': row.id,
                    'erp_id': row.erp_id,
                    'name': row.name,
                    'designation': row.designation,
                    'section': row.section,
                    'uid': row.uid,
                    'user_id': row.user_id,
                    'timestamp': '-' if row.timestamp is None else row.timestamp,
                    'late':  row.lateintime,
                    'status': '-' if row.status is None else row.status,
                    'flag': 'Present' if row.uid is not None else 'Absent',
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
        if session is None:
            return JsonResponse({"error": "Database session could not be created"}, status=500)
        records = []
        try:
            query = text("""
                SELECT
                    e.id AS id,
                    e.erp_id AS erp_id,
                    e.name AS name,
                    a.uid AS uid,
                    e.hris_id AS user_id,
                    d.title AS designation,
                    s.name AS section,
                    a.timestamp AS timestamp,
                    a.status AS status,
                    a.lateintime AS lateintime,
                    a.punch AS punch
                FROM employees e
                LEFT JOIN sections s ON s.id = e.section_id
                LEFT JOIN designations d ON d.id = e.designation_id
                LEFT JOIN attendance a ON e.hris_id = a.user_id AND CAST(a.timestamp AS DATE) BETWEEN :fromdate AND :todate
               WHERE a.status IN ('Checked In', 'Checked Out', 'Early Checked Out')
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
                query, {"fromdate": fromdate, "todate": todate})
            print('baseer',result)
            for row in result:

                records.append({
                    'id': row.id,
                    'erp_id': row.erp_id,
                    'uid': row.uid,
                    'user_id': row.user_id,
                    'name': row.name,
                    'timestamp': '-' if row.timestamp is None else row.timestamp,
                    # Assuming 9 AM is the cutoff for being on time
                    'late': '-' if row.uid is None else row.lateintime,
                    'status': '-' if row.status is None else row.status,
                    'flag': 'Present' if row.uid is not None else 'Absent',
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
