from django.urls import path
from .views import get_leave_requests, create_official_work_request

urlpatterns = [
    path("get/", get_leave_requests, name="get_leave_requests"),
    path("apply/", create_official_work_request, name="create_official_work_request"),

]