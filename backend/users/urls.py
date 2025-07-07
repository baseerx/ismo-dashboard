from django.urls import path, include

from .views import UsersView, EmployeesView
urlpatterns = [
    path('get/', UsersView.get),  # Include the users app URLs
    path('employees/', EmployeesView.get),  # Include the employees app URLs
    path('create_user/', UsersView.create_user),  # Include the create user URL
    path('login/',UsersView.login_user),  # Include the login URL
]