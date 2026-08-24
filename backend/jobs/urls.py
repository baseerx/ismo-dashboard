from django.urls import path

from . import views

urlpatterns = [
    # Open vacancies for the application form's dropdown.
    path('requisitions/', views.requisitions),
    # What `employees` already knows about the person filling in the form.
    path('application-profile/', views.application_profile),
    path('applications/', views.my_applications),
    path('applications/create/', views.create_application),
]
