from django.urls import path, include

from .views import UsersView
urlpatterns = [
    path('get/', UsersView.get),  # Include the users app URLs
    
]