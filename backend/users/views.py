from django.shortcuts import render
from django.http import JsonResponse
from .models import Users,Employees  # Assuming you have a Users model defined
# Create your views here.
class UsersView:
    def get(request):
        records=Users.objects.all()
        records_list = records.values(
            'uid', 'user_id', 'name', 'privilege', 'password', 'group_id', 'card'
        )
        users_list = list(records_list)
        return JsonResponse(users_list, safe=False)  # Return as JSON response

class EmployeesView:
    def get(request):
        records = Employees.objects.all()
        records_list = records.values(
            'id', 'erp_id', 'hris_id', 'name', 'cnic', 'gender', 'section_id', 'location_id', 'grade_id', 'designation_id', 'position'
        )
        employees_list = list(records_list)
        return JsonResponse(employees_list, safe=False)  # Return as JSON response