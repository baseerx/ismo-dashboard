from django.urls import path, include

from .views import UsersView, EmployeesView
urlpatterns = [
    path('get/', UsersView.get),  # Include the users app URLs
    path('employees/', EmployeesView.get),  # Include the employees app URLs
    # Include the employees app URLs
    path('info/', EmployeesView.employees_summary),
    path('create_user/', UsersView.create_user),  # Include the create user URL
    path('login/',UsersView.login_user),  # Include the login URL
    path('change-password/',UsersView.change_password),  # Include the change password URL
    path('get_auth_users/', UsersView.auth_users),  # Include the login URL
    path('delete_user/<int:user_id>/', UsersView.delete_user),  # Include the login URL
]