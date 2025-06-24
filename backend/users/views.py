from django.shortcuts import render
from django.http import JsonResponse
from .models import Users  # Assuming you have a Users model defined
# Create your views here.
class UsersView:
    def get(request):
        records=Users.objects.all()
        records_list = records.values(
            'uid', 'user_id', 'name', 'privilege', 'password', 'group_id', 'card'
        )
        users_list = list(records_list)
        return JsonResponse(users_list, safe=False)  # Return as JSON response