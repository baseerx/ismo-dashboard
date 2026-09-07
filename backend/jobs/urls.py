from django.urls import path

from . import jd_views, requisition_views, views, reports_views

urlpatterns = [
    # --- the application form ---------------------------------------------
    # Vacancies that can still be applied for.
    path('requisitions/', views.requisitions),
    # What `employees` already knows about the person filling in the form.
    path('application-profile/', views.application_profile),
    path('applications/', views.my_applications),
    path('applications/create/', views.create_application),

    # --- maintaining vacancies (Internal Recruitment Portal) --------------
    # Every vacancy, open or closed, with application counts.
    path('requisitions/manage/', requisition_views.manage_list),
    path('requisitions/create/', requisition_views.create_requisition),
    path('requisitions/<int:requisition_id>/update/', requisition_views.update_requisition),
    path('requisitions/<int:requisition_id>/delete/', requisition_views.delete_requisition),

    # --- the job description library --------------------------------------
    # Active descriptions, for the picker on the vacancy screen.
    path('descriptions/', jd_views.description_list),
    # Every description, with how many vacancies use each.
    path('descriptions/manage/', jd_views.manage_list),
    path('descriptions/create/', jd_views.create_description),
    path('descriptions/<int:description_id>/update/', jd_views.update_description),
    path('descriptions/<int:description_id>/delete/', jd_views.delete_description),

    path('applications/manage/', reports_views.list_applications_report),
    path('applications/<int:application_id>/detail/', reports_views.application_detail),
    path('applications/<int:application_id>/pdf/', reports_views.application_pdf),
    path('applications/export/zip/', reports_views.applications_zip),
]
