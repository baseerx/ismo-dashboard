from django.urls import path, include
from .views import AssignRightsView
from .chatbot_visibility import get_visibility, set_visibility
from .sidebar import sidebar_menu

urlpatterns = [
    path('create/', AssignRightsView.create),
    path('get/<int:id>/', AssignRightsView.get),
    # What the sidebar shows: granted rights plus pages every employee sees.
    path('sidebar/<int:id>/', sidebar_menu),
    path('delete/<int:id>/', AssignRightsView.delete),
    # Whether the HR Assistant launcher is shown, and to whom.
    path('chatbot-visibility/', get_visibility),
    path('chatbot-visibility/set/', set_visibility),
]
