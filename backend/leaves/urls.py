from django.urls import path
from .views import get_leave_requests, create_leave_request

urlpatterns = [
    path("get/", get_leave_requests, name="get_leave_requests"),
    path("apply/", create_leave_request, name="create_leave_request"),
]