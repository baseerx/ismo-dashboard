from django.shortcuts import render
from django.http import JsonResponse
from .models import Users, Employees  # Assuming you have a Users model defined
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
import json
import os
import datetime
from django.utils.dateparse import parse_date
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.contrib.auth import authenticate
from django.conf import settings
import jwt
from addtouser.models import CustomUser
# Assuming you have an AssignRights model defined
from assignrights.models import AssignRightsModel
from datetime import date, timedelta
# Import CustomUser from another app named 'addtousers'
from addtouser.models import CustomUser
# Import LeaveModel from another app named 'attendance'
from attendance.models import Attendance
from sections.models import Grades, Sections
from holidays.models import Holiday
from sqlalchemy import text
from db import SessionLocal
import random
import requests
# Create your views here.


class UsersView:
    @require_GET
    def get(request):
        records = Users.objects.all()
        records_list = records.values(
            'uid', 'user_id', 'name', 'privilege', 'password', 'group_id', 'card'
        )
        users_list = list(records_list)
        return JsonResponse(users_list, safe=False)  # Return as JSON response

    @csrf_exempt
    @require_POST
    def create_user(request):
        data = json.loads(request.body.decode('utf-8'))

        username = data.get('username', '')
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        erpid = data.get('erpid', '')
        email = data.get('email', '')
        password = data.get('password', '')
        verify_password = data.get('verify_password', '')
        is_staff = str(data.get('is_staff', 'false')).lower() == 'true'
        is_active = str(data.get('is_active', 'true')).lower() == 'true'
        is_superuser = str(data.get('is_superuser', 'false')).lower() == 'true'
        date_joined_str = data.get('date_joined', '')
        date_joined = parse_date(
            date_joined_str) if date_joined_str else datetime.date.today()

        if password != verify_password:
            return JsonResponse({'success': False, 'error': 'Passwords do not match'}, status=400)

        if not username or not password:
            return JsonResponse({'success': False, 'error': 'Username and password are required'}, status=400)

        if User.objects.filter(username=username).exists():
            return JsonResponse({'success': False, 'error': 'Username already exists'}, status=400)

        user = User.objects.create(
            password=make_password(password),
            last_login=None,
            is_superuser=is_superuser,
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            is_staff=is_staff,
            is_active=is_active,
            date_joined=date_joined
        )
        profile_tbl = CustomUser.objects.create(
            authid=user.pk,
            erpid=erpid)
        if profile_tbl is not None:
            return JsonResponse({'success': True, 'user_id': user.pk, 'profile_id': profile_tbl.pk})
        else:
            user.delete()
            return JsonResponse({'success': False, 'error': 'Failed to create user profile'}, status=500)

    @csrf_exempt
    @require_POST
    def signup_user(request):
        data = json.loads(request.body.decode('utf-8'))

        username = data.get('username', '')
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        erpid = data.get('erpid', '')
        email = data.get('email', '')
        password = data.get('password', '')
        verify_password = data.get('verify_password', '')
        is_superuser = str(data.get('is_superuser', 'false')).lower() == 'true'
        date_joined_str = data.get('date_joined', '')
        date_joined = parse_date(
            date_joined_str) if date_joined_str else datetime.date.today()

        if password != verify_password:
            return JsonResponse({'success': False, 'error': 'Passwords do not match'}, status=400)

        if not username or not password:
            return JsonResponse({'success': False, 'error': 'Username and password are required'}, status=400)

        if User.objects.filter(username=username).exists():
            return JsonResponse({'success': False, 'error': 'Username already exists'}, status=400)

        if CustomUser.objects.filter(erpid=erpid).exists():
            return JsonResponse({'success': False, 'error': 'ERP ID already exists'}, status=400)        

        user = User.objects.create(
            password=make_password(password),
            last_login=None,
            is_superuser=is_superuser,
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            is_staff=1,
            is_active=1,
            date_joined=date_joined
        )

        profile_tbl = CustomUser.objects.create(
            authid=user.pk,
            erpid=erpid)

        AssignRightsModel.objects.create(
            user_id=user.pk,
            main_menu=5,  # Assuming 5 is the main menu ID for 'Users'
            sub_menu=3   # Assuming 3 is the sub menu ID for 'Create User'
        )
        # AssignRightsModel.objects.create(
        #     user_id=user.pk,
        #     main_menu=8,  # Assuming 5 is the main menu ID for 'Users'
        #     sub_menu=18   # Assuming 3 is the sub menu ID for 'Create User'
        # )
        AssignRightsModel.objects.create(
            user_id=user.pk,
            main_menu=9,  # Assuming 5 is the main menu ID for 'Users'
            sub_menu=12   # Assuming 3 is the sub menu ID for 'Create User'
        )
        AssignRightsModel.objects.create(
            user_id=user.pk,
            main_menu=9,  # Assuming 5 is the main menu ID for 'Users'
            sub_menu=16   # Assuming 3 is the sub menu ID for 'Create User'
        )

        if profile_tbl is not None:
            return JsonResponse({'success': True, 'user_id': user.pk, 'profile_id': profile_tbl.pk})
        else:
            user.delete()
            return JsonResponse({'success': False, 'error': 'Failed to create user profile'}, status=500)

    @csrf_exempt
    @require_POST
    def login_user(request):
        data = json.loads(request.body.decode('utf-8'))
        email = data.get('email', '')
        password = data.get('password', '')

        try:
            user_obj = User.objects.get(email=email,is_active=1)
            username = user_obj.username
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Invalid credentials'}, status=401)

        user = authenticate(username=username, password=password)
        # print(f"User authenticated: {user}")  # Debugging line to check user authentication
        if user is not None:
            erpid = CustomUser.objects.filter(
                authid=user.pk).values_list('erpid', flat=True).first()
            employee = Employees.objects.filter(erp_id=erpid).values(
                'grade_id', 'section_id', 'name', 'gender'
            ).first()
            grade = employee.get('grade_id') if employee else None
            section_id = employee.get('section_id') if employee else None
            section_name = Sections.objects.filter(id=section_id).values_list(
                'name', flat=True).first() if section_id else None
            if erpid is not None:
                # return user details alongside token and success status
                payload = {
                    'success': True,
                    'user_id': user.pk,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'grade_id': grade,
                    'erpid': erpid,
                    'section_id': section_id,
                    'section_name': section_name,
                    'employee_name': employee.get('name') if employee else None,
                    'gender': employee.get('gender') if employee else None,
                    'email': user.email,
                    'is_staff': user.is_staff,
                    'is_active': user.is_active,
                    'is_superuser': user.is_superuser,
                    'expires': (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=getattr(settings, "JWT_EXP_DELTA_SECONDS", 3600))).isoformat(),
                }
                token = jwt.encode(
                    payload, settings.SECRET_KEY, algorithm='HS256')
                payload['token'] = token
                return JsonResponse({'success': True, 'user': payload}, status=200)
        else:
            return JsonResponse({'success': False, 'error': 'Invalid credentials'}, status=401)

    @require_GET
    def auth_users(request):
        records = User.objects.all()
        records_list = records.values(
            'id', 'username', 'first_name', 'last_name', 'email', 'is_staff', 'is_active', 'is_superuser'
        )
        # Add 'success': True and rename 'id' to 'user_id' for each user
        users_list = [
            {
                'success': True,
                'user_id': user['id'],
                'username': user['username'],
                'first_name': user['first_name'],
                'last_name': user['last_name'],
                'email': user['email'],
                'is_staff': user['is_staff'],
                'is_active': user['is_active'],
                'is_superuser': user['is_superuser'],
            }
            for user in records_list
        ]
        users_list = list(records_list)
        return JsonResponse(users_list, safe=False)  # Return as JSON response

    @csrf_exempt
    @require_POST
    def delete_user(request, user_id):
        if not user_id:
            return JsonResponse({'success': False, 'error': 'User ID is required'}, status=400)

        try:
            user = User.objects.get(pk=user_id)
            profile = CustomUser.objects.filter(authid=user_id).first()
            if profile:
                profile.delete()
            user.delete()
            return JsonResponse({'success': True}, status=200)
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User not found'}, status=404)
   
    @csrf_exempt
    @require_POST
    def reset_password(request, user_id):
        if not user_id:
            return JsonResponse({'success': False, 'error': 'User ID is required'}, status=400)

        try:
            user = User.objects.get(pk=user_id)
            password = user.email
            user.set_password(password)
            user.save()
            return JsonResponse({'success': True}, status=200)
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User not found'}, status=404)

    @csrf_exempt
    @require_POST
    def change_password(request):
        data = json.loads(request.body.decode('utf-8'))
        user_id = data.get('user_id')
        old_password = data.get('old_password')
        new_password1 = data.get('new_password1')
        new_password2 = data.get('new_password2')
        if not user_id or not old_password or not new_password1 or not new_password2:
            return JsonResponse({'success': False, 'error': 'All fields are required'}, status=400)
        try:
            user = User.objects.get(pk=user_id)
            if not user.check_password(old_password):
                return JsonResponse({'success': False, 'error': 'Old password is incorrect'}, status=400)
            if new_password1 != new_password2:
                return JsonResponse({'success': False, 'error': 'New passwords do not match'}, status=400)
            user.set_password(new_password1)
            user.save()
            return JsonResponse({'success': True, 'message': 'Password changed successfully'}, status=200)
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User not found'}, status=404)


class EmployeesView:
    def get(request):
        records = Employees.objects.all()
        records_list = records.values(
            'id', 'erp_id', 'hris_id', 'name', 'cnic', 'gender', 'section_id', 'location_id', 'grade_id', 'designation_id', 'position', 'flag'
        )
        employees_list = list(records_list)

        # The grade's own label ("G-09"), so callers can show and rank seniority
        # without hardcoding a mapping from grade_id. Eleven rows, fetched once.
        grade_names = dict(Grades.objects.values_list('id', 'name'))
        for employee in employees_list:
            employee['grade'] = grade_names.get(employee.get('grade_id'))

        # Return as JSON response
        return JsonResponse(employees_list, safe=False)

    @require_GET
    def ncc_employees(request):
        url = os.environ.get('SDXP_URL')
        session = SessionLocal()
        shift_employees_response = requests.get(f'{url}/ShiftRoster/GetShiftEmployees')
        try:
            shift_employees = shift_employees_response.json()
        except Exception:
            shift_employees = []
        # Filter only NCC employees
        ncc_employees = [emp for emp in shift_employees if emp.get('Shift_Type') == 'NCC']
        query = text("""
         SELECT
            e.name as empname,
            e.hris_id,
            s.[Sdxp_Username]
          FROM [dbo].[shift_user_map] s JOIN employees e ON e.erp_id= s.ErpID
        """)
        shiftdata = session.execute(query).fetchall()

        # Prepare sets for fast comparison (case-insensitive, strip spaces)
        ncc_names = set(str(emp.get('Name', '')).strip().lower() for emp in ncc_employees if emp.get('Name'))
        ncc_usernames = set(str(emp.get('Name', '')).strip().lower() for emp in ncc_employees if emp.get('Name'))

        matched_employees = []
        for row in shiftdata:
            empname = str(row.empname).strip().lower() if row.empname else ""
            sdxp_username = str(row.Sdxp_Username).strip().lower() if row.Sdxp_Username else ""
            # Compare Sdxp_Username and empname with NCC names
            if empname in ncc_names or sdxp_username in ncc_usernames:
                matched_employees.append({
                    "empname": row.empname,
                    "hris_id": row.hris_id
                })

        # Convert shiftdata to list of dicts (for original output)
        shiftdata_list = [
            dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
            for row in shiftdata
        ]
        return JsonResponse({'matched': matched_employees}, safe=False)
    
    @require_GET
    def rcc_employees(request):
        url = os.environ.get('SDXP_URL')
        session = SessionLocal()
        shift_employees_response = requests.get(f'{url}/ShiftRoster/GetShiftEmployees')
        try:
            shift_employees = shift_employees_response.json()
        except Exception:
            shift_employees = []
        # Filter only NCC employees
        ncc_employees = [emp for emp in shift_employees if emp.get('Shift_Type') == 'RCC']
        query = text("""
         SELECT
            e.name as empname,
            e.hris_id,
            s.[Sdxp_Username]
          FROM [dbo].[shift_user_map] s JOIN employees e ON e.erp_id= s.ErpID
        """)
        shiftdata = session.execute(query).fetchall()

        # Prepare sets for fast comparison (case-insensitive, strip spaces)
        ncc_names = set(str(emp.get('Name', '')).strip().lower() for emp in ncc_employees if emp.get('Name'))
        ncc_usernames = set(str(emp.get('Name', '')).strip().lower() for emp in ncc_employees if emp.get('Name'))

        matched_employees = []
        for row in shiftdata:
            empname = str(row.empname).strip().lower() if row.empname else ""
            sdxp_username = str(row.Sdxp_Username).strip().lower() if row.Sdxp_Username else ""
            # Compare Sdxp_Username and empname with NCC names
            if empname in ncc_names or sdxp_username in ncc_usernames:
                matched_employees.append({
                    "empname": row.empname,
                    "hris_id": row.hris_id
                })

        # Convert shiftdata to list of dicts (for original output)
        shiftdata_list = [
            dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
            for row in shiftdata
        ]
        return JsonResponse({'matched': matched_employees}, safe=False)

    @require_GET
    def get_employees(request):
        try:
            session = SessionLocal()

            # SQL with joins to fetch all employee attributes + section/location/grade/designation
            employees_query = text('''
                SELECT e.id, e.erp_id, e.hris_id, e.name, e.cnic, e.gender, 
                    e.section_id, e.location_id, e.grade_id, e.designation_id, 
                    e.position, e.flag,
                    s.name AS section_name,
                    l.name AS location_name,
                    g.name AS grade_name,
                    d.title AS designation_title
                FROM employees e
                LEFT JOIN sections s ON e.section_id = s.id
                LEFT JOIN locations l ON e.location_id = l.id
                LEFT JOIN grades g ON e.grade_id = g.id
                LEFT JOIN designations d ON e.designation_id = d.id
                
            ''')

            employees_data = session.execute(employees_query).fetchall()

            employees = [
                {
                    "id": row.id,
                    "erp_id": row.erp_id,
                    "hris_id": row.hris_id,
                    "name": row.name,
                    "cnic": row.cnic,
                    "gender": row.gender,
                    "position": row.position,
                    "flag": row.flag,
                    "section": {
                        "id": row.section_id,
                        "name": row.section_name
                    },
                    "location": {
                        "id": row.location_id,
                        "name": row.location_name
                    },
                    "grade": {
                        "id": row.grade_id,
                        "name": row.grade_name
                    },
                    "designation": {
                        "id": row.designation_id,
                        "title": row.designation_title
                    }
                }
                for row in employees_data
            ]

            return JsonResponse({"success": True, "employees": employees}, status=200)

        except Exception as e:
            import traceback
            print("Unexpected error in get_employees:", str(e))
            traceback.print_exc()
            return JsonResponse({"success": False, "error": str(e)}, status=500)

        finally:
            session.close()

    @csrf_exempt
    @require_POST
    def delete_employee(request, employee_id):
        if not employee_id:
            return JsonResponse({'success': False, 'error': 'Employee ID is required'}, status=400)

        try:
            employee = Employees.objects.get(pk=employee_id)
            authid= CustomUser.objects.filter(erpid=employee.erp_id).values_list('authid', flat=True).first()
     
            user= User.objects.get(pk=authid)
    
            if employee.flag==0:           
                user.is_active=1
                employee.flag=1
            else:
                employee.flag=0
                user.is_active=0
            user.save()
            employee.save()
            return JsonResponse({'success': True}, status=200)
        except Employees.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Employee not found'}, status=404)

    @require_GET
    def employees_summary(request):
        today = date.today()

        total_employees = Employees.objects.filter(flag=1).count()

        # Get unique user_ids from attendance where timestamp is today
        present_user_ids = Attendance.objects.filter(
            timestamp__date=today
        ).values_list('user_id', flat=True).distinct()

        present_count = present_user_ids.count()
        absent_count = total_employees - present_count

        summary = {
            "total_employees": total_employees,
            "present_today": present_count,
            "absent_today": absent_count
        }

        return JsonResponse(summary)

    @require_GET
    def dashboard_stats(request):
        erp_id = request.GET.get("erp_id")
        scope = request.GET.get("scope", "section")
        org_wide = (scope == "org")

        if not erp_id:
            return JsonResponse({"error": "erp_id is required"}, status=400)

        requester = Employees.objects.filter(erp_id=erp_id).values(
            "section_id"
        ).first()
        if not requester:
            return JsonResponse({"error": "Employee not found"}, status=404)

        section_id = requester["section_id"]
        section_name = Sections.objects.filter(id=section_id).values_list(
            "name", flat=True
        ).first()

        today = date.today()

        # Pakistan Financial Year: 1 July -> 30 June
        if today.month >= 7:
            fy_start = date(today.year, 7, 1)
            fy_end = date(today.year + 1, 6, 30)
        else:
            fy_start = date(today.year - 1, 7, 1)
            fy_end = date(today.year, 6, 30)

        # 20 calendar days back yields ~14 working days once weekends and
        # holidays are removed.
        trend_start = today - timedelta(days=19)
        month_trend_start = (today.replace(day=1) - timedelta(days=150)).replace(day=1)

        today_holiday = Holiday.objects.filter(date=today).first()
        is_holiday_today = today_holiday is not None
        is_weekend_today = today.weekday() in (5, 6)

        section_clause = "" if org_wide else "AND e.section_id = :section_id"
        base_params = {} if org_wide else {"section_id": section_id}

        session = SessionLocal()
        try:
            # --------------------------------------------------
            # EMPLOYEE COUNTS (total / gender / grade breakdown)
            # --------------------------------------------------
            emp_row = session.execute(text(f"""
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN e.gender = 'M' THEN 1 ELSE 0 END) AS male,
                    SUM(CASE WHEN e.gender = 'F' THEN 1 ELSE 0 END) AS female
                FROM employees e
                WHERE e.flag = 1 {section_clause}
            """), base_params).first()

            grade_rows = session.execute(text(f"""
                SELECT g.name AS grade, COUNT(*) AS count
                FROM employees e
                JOIN grades g ON g.id = e.grade_id
                WHERE e.flag = 1 {section_clause}
                GROUP BY g.name
                ORDER BY count DESC
            """), base_params).fetchall()

            # --------------------------------------------------
            # ATTENDANCE TODAY (grouped by section for the org view)
            # --------------------------------------------------
            att_today_rows = session.execute(text(f"""
                WITH employees_data AS (
                    SELECT e.erp_id, e.hris_id, s.id AS section_id, ISNULL(s.name, '-') AS section
                    FROM employees e
                    LEFT JOIN sections s ON s.id = e.section_id
                    WHERE e.flag = 1 {section_clause}
                ),
                attendance_today AS (
                    SELECT DISTINCT user_id FROM attendance WHERE CAST(timestamp AS DATE) = :today
                ),
                leave_today AS (
                    SELECT erp_id FROM leaves
                    WHERE status = 'approved'
                    AND CAST(start_date AS DATE) <= :today AND CAST(end_date AS DATE) >= :today
                ),
                official_today AS (
                    SELECT erp_id FROM official_work_leaves
                    WHERE status = 'approved'
                    AND CAST(start_date AS DATE) <= :today AND CAST(end_date AS DATE) >= :today
                )
                SELECT
                    ed.section_id, ed.section,
                    COUNT(*) AS total,
                    SUM(CASE WHEN a.user_id IS NOT NULL THEN 1 ELSE 0 END) AS present,
                    SUM(CASE WHEN a.user_id IS NULL AND l.erp_id IS NOT NULL THEN 1 ELSE 0 END) AS on_leave,
                    SUM(CASE
                            WHEN a.user_id IS NULL AND l.erp_id IS NULL AND ow.erp_id IS NOT NULL
                            THEN 1 ELSE 0
                        END) AS official_work,
                    SUM(CASE
                            WHEN a.user_id IS NOT NULL THEN 0
                            WHEN l.erp_id IS NOT NULL THEN 0
                            WHEN ow.erp_id IS NOT NULL THEN 0
                            WHEN :is_holiday_today = 1 THEN 0
                            WHEN :is_weekend_today = 1 THEN 0
                            ELSE 1
                        END) AS absent
                FROM employees_data ed
                LEFT JOIN attendance_today a ON a.user_id = ed.hris_id
                LEFT JOIN leave_today l ON l.erp_id = ed.erp_id
                LEFT JOIN official_today ow ON ow.erp_id = ed.erp_id
                GROUP BY ed.section_id, ed.section
                ORDER BY ed.section
            """), {
                **base_params,
                "today": today,
                "is_holiday_today": 1 if is_holiday_today else 0,
                "is_weekend_today": 1 if is_weekend_today else 0,
            }).fetchall()

            # --------------------------------------------------
            # ATTENDANCE TREND (working days only, present vs total)
            #
            # Saturdays, Sundays and public holidays are left out entirely.
            # Nobody is expected in on those days, so including them drew a
            # dip to zero every weekend that read as mass absence.
            #
            # The weekday test is arithmetic rather than DATEPART(WEEKDAY),
            # which shifts with the connection's DATEFIRST setting.
            # 1900-01-01 was a Monday, so the modulo gives 0=Mon .. 6=Sun.
            # --------------------------------------------------
            trend_rows = session.execute(text(f"""
                WITH date_range AS (
                    SELECT DATEADD(DAY, v.number, :trend_start) AS att_date
                    FROM master..spt_values v
                    WHERE v.type = 'P'
                      AND DATEADD(DAY, v.number, :trend_start) <= :today
                      AND DATEDIFF(DAY, '19000101',
                                   DATEADD(DAY, v.number, :trend_start)) % 7 NOT IN (5, 6)
                      AND NOT EXISTS (
                          SELECT 1 FROM public_holidays h
                          WHERE h.date = CAST(DATEADD(DAY, v.number, :trend_start) AS DATE)
                      )
                ),
                employees_data AS (
                    SELECT e.erp_id, e.hris_id
                    FROM employees e
                    WHERE e.flag = 1 {section_clause}
                ),
                attendance_days AS (
                    SELECT DISTINCT user_id, CAST(timestamp AS DATE) AS att_date
                    FROM attendance
                    WHERE timestamp >= :trend_start AND timestamp < DATEADD(DAY, 1, :today)
                ),
                -- Leave and official work spans expanded to one row per covered
                -- working day, so the SUM below can join them. SQL Server will
                -- not allow a correlated subquery inside an aggregate.
                leave_days AS (
                    SELECT DISTINCT l.erp_id, dr.att_date
                    FROM leaves l
                    JOIN date_range dr
                        ON CAST(l.start_date AS DATE) <= dr.att_date
                       AND CAST(l.end_date AS DATE) >= dr.att_date
                    WHERE l.status = 'approved'
                ),
                official_days AS (
                    SELECT DISTINCT ow.erp_id, dr.att_date
                    FROM official_work_leaves ow
                    JOIN date_range dr
                        ON CAST(ow.start_date AS DATE) <= dr.att_date
                       AND CAST(ow.end_date AS DATE) >= dr.att_date
                    WHERE ow.status = 'approved'
                )
                SELECT
                    dr.att_date,
                    COUNT(*) AS total,
                    SUM(CASE WHEN a.user_id IS NOT NULL THEN 1 ELSE 0 END) AS present,
                    -- Absent means the same thing here as it does on the tile:
                    -- no punch, and no approved leave or official work covering
                    -- the day. Total minus present would have counted anyone on
                    -- approved leave as absent.
                    SUM(CASE
                            WHEN a.user_id IS NOT NULL THEN 0
                            WHEN ld.erp_id IS NOT NULL THEN 0
                            WHEN od.erp_id IS NOT NULL THEN 0
                            ELSE 1
                        END) AS absent
                FROM employees_data ed
                CROSS JOIN date_range dr
                LEFT JOIN attendance_days a
                    ON a.user_id = ed.hris_id AND a.att_date = dr.att_date
                LEFT JOIN leave_days ld
                    ON ld.erp_id = ed.erp_id AND ld.att_date = dr.att_date
                LEFT JOIN official_days od
                    ON od.erp_id = ed.erp_id AND od.att_date = dr.att_date
                GROUP BY dr.att_date
                ORDER BY dr.att_date
            """), {**base_params, "trend_start": trend_start, "today": today}).fetchall()

            # --------------------------------------------------
            # LEAVE STATS
            # --------------------------------------------------
            leave_pending = session.execute(text(f"""
                SELECT COUNT(*) AS pending
                FROM leaves l
                JOIN employees e ON e.erp_id = l.erp_id
                WHERE l.status = 'pending' {section_clause}
            """), base_params).scalar()

            leave_by_type_rows = session.execute(text(f"""
                SELECT l.leave_type, COUNT(*) AS requests, SUM(l.total_days) AS days
                FROM leaves l
                JOIN employees e ON e.erp_id = l.erp_id
                WHERE l.status IN ('approved', 'pending')
                AND l.start_date <= :fy_end AND l.end_date >= :fy_start
                {section_clause}
                GROUP BY l.leave_type
                ORDER BY days DESC
            """), {**base_params, "fy_start": fy_start, "fy_end": fy_end}).fetchall()

            leave_monthly_rows = session.execute(text(f"""
                SELECT YEAR(l.start_date) AS yr, MONTH(l.start_date) AS mo, SUM(l.total_days) AS days
                FROM leaves l
                JOIN employees e ON e.erp_id = l.erp_id
                WHERE l.status IN ('approved', 'pending')
                AND l.start_date >= :month_trend_start
                {section_clause}
                GROUP BY YEAR(l.start_date), MONTH(l.start_date)
                ORDER BY yr, mo
            """), {**base_params, "month_trend_start": month_trend_start}).fetchall()

            # --------------------------------------------------
            # OFFICIAL WORK STATS
            # --------------------------------------------------
            official_pending = session.execute(text(f"""
                SELECT COUNT(*) AS pending
                FROM official_work_leaves ow
                JOIN employees e ON e.erp_id = ow.erp_id
                WHERE ow.status = 'pending' {section_clause}
            """), base_params).scalar()

            official_by_type_rows = session.execute(text(f"""
                SELECT ow.leave_type, COUNT(*) AS requests
                FROM official_work_leaves ow
                JOIN employees e ON e.erp_id = ow.erp_id
                WHERE ow.status IN ('approved', 'pending')
                AND ow.start_date <= :fy_end AND ow.end_date >= :fy_start
                {section_clause}
                GROUP BY ow.leave_type
                ORDER BY requests DESC
            """), {**base_params, "fy_start": fy_start, "fy_end": fy_end}).fetchall()

            official_monthly_rows = session.execute(text(f"""
                SELECT YEAR(ow.start_date) AS yr, MONTH(ow.start_date) AS mo, COUNT(*) AS requests
                FROM official_work_leaves ow
                JOIN employees e ON e.erp_id = ow.erp_id
                WHERE ow.status IN ('approved', 'pending')
                AND ow.start_date >= :month_trend_start
                {section_clause}
                GROUP BY YEAR(ow.start_date), MONTH(ow.start_date)
                ORDER BY yr, mo
            """), {**base_params, "month_trend_start": month_trend_start}).fetchall()

            # --------------------------------------------------
            # ORG-WIDE SECTION BREAKDOWN (admin only)
            # --------------------------------------------------
            by_section = []
            if org_wide:
                section_emp_rows = session.execute(text("""
                    SELECT s.id AS section_id, s.name AS section_name,
                        COUNT(e.id) AS total_employees
                    FROM sections s
                    LEFT JOIN employees e ON e.section_id = s.id AND e.flag = 1
                    GROUP BY s.id, s.name
                    ORDER BY s.name
                """)).fetchall()

                pending_leave_by_section = {
                    row.section_id: row.pending for row in session.execute(text("""
                        SELECT e.section_id, COUNT(*) AS pending
                        FROM leaves l
                        JOIN employees e ON e.erp_id = l.erp_id
                        WHERE l.status = 'pending'
                        GROUP BY e.section_id
                    """)).fetchall()
                }

                pending_official_by_section = {
                    row.section_id: row.pending for row in session.execute(text("""
                        SELECT e.section_id, COUNT(*) AS pending
                        FROM official_work_leaves ow
                        JOIN employees e ON e.erp_id = ow.erp_id
                        WHERE ow.status = 'pending'
                        GROUP BY e.section_id
                    """)).fetchall()
                }

                attendance_by_section = {row.section_id: row for row in att_today_rows}

                for row in section_emp_rows:
                    att_row = attendance_by_section.get(row.section_id)
                    by_section.append({
                        "section_id": row.section_id,
                        "section_name": row.section_name,
                        "total_employees": row.total_employees,
                        "present_today": att_row.present if att_row else 0,
                        "on_leave_today": att_row.on_leave if att_row else 0,
                        "official_work_today": att_row.official_work if att_row else 0,
                        "absent_today": att_row.absent if att_row else 0,
                        "pending_leaves": pending_leave_by_section.get(row.section_id, 0),
                        "pending_official_work": pending_official_by_section.get(row.section_id, 0),
                    })

            attendance_today_total = {
                "total": sum(r.total for r in att_today_rows),
                "present": sum(r.present for r in att_today_rows),
                "on_leave": sum(r.on_leave for r in att_today_rows),
                "official_work": sum(r.official_work for r in att_today_rows),
                "absent": sum(r.absent for r in att_today_rows),
            }

            upcoming_holidays = [
                {"name": h.name, "date": h.date.isoformat()}
                for h in Holiday.objects.filter(date__gte=today).order_by("date")[:5]
            ]

            response = {
                "scope": "org" if org_wide else "section",
                "section_id": section_id,
                "section_name": section_name,
                "today": today.isoformat(),
                "is_weekend": is_weekend_today,
                "is_holiday": is_holiday_today,
                "holiday_name": today_holiday.name if today_holiday else None,
                "financial_year": f"{fy_start.strftime('%d-%b-%Y')} to {fy_end.strftime('%d-%b-%Y')}",
                "employees": {
                    "total": emp_row.total or 0,
                    "male": emp_row.male or 0,
                    "female": emp_row.female or 0,
                    "by_grade": [{"grade": r.grade, "count": r.count} for r in grade_rows],
                },
                "attendance_today": attendance_today_total,
                "attendance_trend": [
                    {
                        "date": r.att_date.isoformat(),
                        "total": r.total,
                        "present": r.present,
                        "absent": r.absent or 0,
                    }
                    for r in trend_rows
                ],
                # Mon-Fri, minus public holidays. Weekends are non-working days
                # here, so they are excluded from every absence figure.
                "trend_basis": "working days (Mon-Fri, excluding public holidays)",
                "is_working_day": not (is_weekend_today or is_holiday_today),
                "leaves": {
                    "pending": leave_pending or 0,
                    "by_type": [
                        {"type": r.leave_type, "requests": r.requests, "days": r.days or 0}
                        for r in leave_by_type_rows
                    ],
                    "monthly_trend": [
                        {"month": f"{r.yr:04d}-{r.mo:02d}", "days": r.days or 0}
                        for r in leave_monthly_rows
                    ],
                },
                "official_work": {
                    "pending": official_pending or 0,
                    "by_type": [
                        {"type": r.leave_type, "requests": r.requests}
                        for r in official_by_type_rows
                    ],
                    "monthly_trend": [
                        {"month": f"{r.yr:04d}-{r.mo:02d}", "requests": r.requests}
                        for r in official_monthly_rows
                    ],
                },
                "upcoming_holidays": upcoming_holidays,
                "by_section": by_section,
            }

            return JsonResponse(response, status=200)

        finally:
            session.close()

    @staticmethod
    def generate_random_hris_id(existing_ids):
        existing_ids_set = set(existing_ids)
        while True:
            new_id = random.randint(10000, 99999)
            if new_id not in existing_ids_set:
                return new_id

    @require_GET
    def get_details(request):
        sections_data = Sections.objects.all().values('id', 'name')
        sections = [
            {
                "id": section['id'],
                "name": section['name']
            }
            for section in sections_data
        ]

        # fetching location data
        location_query = text('''
            SELECT id, name FROM locations
        ''')
        grade_query = text('''
            SELECT id, name FROM grades
        ''')
        designation_query = text('''
            SELECT id, title FROM designations
        ''')
        session = SessionLocal()
        location_data = session.execute(location_query).fetchall()
        grade_data = session.execute(grade_query).fetchall()
        designation_data = session.execute(designation_query).fetchall()
        designations = [
            {
                "id": designation.id,
                "title": designation.title
            }
            for designation in designation_data
        ]
        grades = [
            {
                "id": grade.id,
                "name": grade.name
            }
            for grade in grade_data
        ]
        locations = [
            {
                "id": location.id,
                "name": location.name
            }
            for location in location_data
        ]
        # generate random HRIS id which is not in column
        existing_hris_ids = Employees.objects.values_list('hris_id', flat=True)
        new_hris_id = EmployeesView.generate_random_hris_id(existing_hris_ids)
        return JsonResponse({"success": True, "sections": sections, "locations": locations, "grades": grades, "designations": designations, "new_hris_id": new_hris_id})

    @csrf_exempt
    @require_POST
    def create_employee(request):
        data = json.loads(request.body.decode('utf-8'))
        # Validate required fields
        required_fields = [
            'erp_id', 'hris_id', 'name', 'cnic', 'gender',
            'section_id', 'location_id', 'grade_id', 'designation_id', 'position'
        ]
        for field in required_fields:
            if field not in data or data[field] in [None, ""]:
                return JsonResponse({"success": False, "error": f"Field '{field}' is required"}, status=400)

        try:
            employee = Employees.objects.create(
                erp_id=str(data['erp_id']),
                hris_id=int(data.get('hris_id', 0)),
                name=data.get('name', ''),
                cnic=data.get('cnic', ''),
                gender=data.get('gender', ''),
                section_id=int(data['section_id']),
                location_id=int(data['location_id']),
                grade_id=int(data['grade_id']),
                designation_id=int(data['designation_id']),
                position=data['position'],
                flag=1 if data.get('flag', False) else 0
            )
            return JsonResponse({"success": True, "message": "Employee created successfully", "employee_id": employee.pk}, status=201)
        except KeyError as e:
            return JsonResponse({"success": False, "error": f"Missing required field: {str(e)}"}, status=400)
        except ValueError as e:
            return JsonResponse({"success": False, "error": f"Invalid value: {str(e)}"}, status=400)

        except Exception as e:
            import traceback
            print("Unexpected error:", str(e))
            traceback.print_exc()   # <-- shows full traceback in console
            return JsonResponse({"success": False, "error": str(e)}, status=500)

    @csrf_exempt
    @require_POST
    def update_employee(request, employee_id):
        if not employee_id:
            return JsonResponse({"success": False, "error": "Employee ID is required"}, status=400)

        try:
            data = json.loads(request.body.decode('utf-8'))
        except Exception:
            return JsonResponse({"success": False, "error": "Invalid JSON format"}, status=400)

        # hris_id is deliberately excluded: it is assigned once at creation and
        # must never change on edit. Every other field is editable.
        required_fields = [
            'erp_id', 'name', 'cnic', 'gender',
            'section_id', 'location_id', 'grade_id', 'designation_id', 'position'
        ]
        for field in required_fields:
            if field not in data or data[field] in [None, ""]:
                return JsonResponse({"success": False, "error": f"Field '{field}' is required"}, status=400)

        try:
            employee = Employees.objects.get(pk=employee_id)
        except Employees.DoesNotExist:
            return JsonResponse({"success": False, "error": "Employee not found"}, status=404)

        try:
            employee.erp_id = str(data['erp_id'])
            employee.name = data.get('name', '')
            employee.cnic = data.get('cnic', '')
            employee.gender = data.get('gender', '')
            employee.section_id = int(data['section_id'])
            employee.location_id = int(data['location_id'])
            employee.grade_id = int(data['grade_id'])
            employee.designation_id = int(data['designation_id'])
            employee.position = data['position']
            employee.flag = 1 if data.get('flag', False) else 0
            # NOTE: employee.hris_id is intentionally left untouched.
            employee.save()
            return JsonResponse({"success": True, "message": "Employee updated successfully"}, status=200)
        except ValueError as e:
            return JsonResponse({"success": False, "error": f"Invalid value: {str(e)}"}, status=400)
        except Exception as e:
            import traceback
            print("Unexpected error in update_employee:", str(e))
            traceback.print_exc()
            return JsonResponse({"success": False, "error": str(e)}, status=500)
