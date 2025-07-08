from django.urls import path, include
from .views import SubMenuView
urlpatterns = [
    path('get/', SubMenuView.get),
    path('create/', SubMenuView.create),
    path('update/<int:id>/', SubMenuView.update),
    path('delete/<int:id>/', SubMenuView.delete),
    path('record/<int:id>/', SubMenuView.get_record),
]
