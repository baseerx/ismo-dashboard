from django.shortcuts import render
from django.http import JsonResponse
from .models import Users,Employees  # Assuming you have a Users model defined
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET,require_POST
import json
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
from datetime import date
from addtouser.models import CustomUser  # Import CustomUser from another app named 'addtousers'
from attendance.models import Attendance  # Import LeaveModel from another app named 'attendance'
# Create your views here.
class UsersView:
    @require_GET
    def get(request):
        records=Users.objects.all()
        records_list = records.values(
            'uid', 'user_id', 'name', 'privilege', 'password', 'group_id', 'card'
        )
        users_list = list(records_list)
        return JsonResponse(users_list, safe=False)  # Return as JSON response
    
    @csrf_exempt
    @require_POST
    def create_user(request):
        data=json.loads(request.body.decode('utf-8'))
        
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
        profile_tbl=CustomUser.objects.create(
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
        data=json.loads(request.body.decode('utf-8'))
        
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
        
        profile_tbl=CustomUser.objects.create(
            authid=user.pk,
            erpid=erpid)
        
        AssignRightsModel.objects.create(
            user_id=user.pk,
            main_menu=5,  # Assuming 5 is the main menu ID for 'Users'
            sub_menu=3   # Assuming 3 is the sub menu ID for 'Create User'
        )
        AssignRightsModel.objects.create(
            user_id=user.pk,
            main_menu=8,  # Assuming 5 is the main menu ID for 'Users'
            sub_menu=18   # Assuming 3 is the sub menu ID for 'Create User'
        )
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
            user_obj = User.objects.get(email=email)
            username = user_obj.username
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Invalid credentials'}, status=401)

        user = authenticate(username=username, password=password)
        # print(f"User authenticated: {user}")  # Debugging line to check user authentication
        if user is not None:
            erpid=CustomUser.objects.filter(authid=user.pk).values_list('erpid', flat=True).first()
            if erpid is not None:
            # return user details alongside token and success status
                payload = {
                    'success': True,
                    'user_id': user.pk,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'erpid': erpid,
                    'email': user.email,
                    'is_staff': user.is_staff,
                    'is_active': user.is_active,
                    'is_superuser': user.is_superuser,
                    'expires': (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=getattr(settings, "JWT_EXP_DELTA_SECONDS", 3600))).isoformat(),
                }
                token=jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
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
            user.delete()
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
            'id', 'erp_id', 'hris_id', 'name', 'cnic', 'gender', 'section_id', 'location_id', 'grade_id', 'designation_id', 'position'
        )
        employees_list = list(records_list)
        return JsonResponse(employees_list, safe=False)  # Return as JSON response

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
    
    
        
