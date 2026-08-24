from django.contrib import admin

from .models import (
    InternalJobApplication,
    InternalJobApplicationEducation,
    InternalJobApplicationExperience,
    InternalJobApplicationSkill,
    JobRequisition,
)


@admin.register(JobRequisition)
class JobRequisitionAdmin(admin.ModelAdmin):
    """HR adds and closes vacancies here.

    Registered so advertising a post needs no screen of its own: closing a
    requisition removes it from the application form while leaving the
    applications already filed against it intact.
    """

    list_display = ("title", "department", "location", "closing_date", "is_open", "created_at")
    list_filter = ("is_open", "department")
    search_fields = ("title", "department", "location")


class EducationInline(admin.TabularInline):
    model = InternalJobApplicationEducation
    extra = 0


class ExperienceInline(admin.TabularInline):
    model = InternalJobApplicationExperience
    extra = 0


class SkillInline(admin.TabularInline):
    model = InternalJobApplicationSkill
    extra = 0


@admin.register(InternalJobApplication)
class InternalJobApplicationAdmin(admin.ModelAdmin):
    """Read side of the review flow: one row per application, degrees inline."""

    list_display = (
        "id", "emp_full_name", "emp_id", "target_job_req",
        "current_dept_code", "current_job_title", "status", "created_at",
    )
    list_filter = ("status", "target_job_req", "preferred_contact_method")
    search_fields = ("emp_full_name", "emp_id", "corporate_email", "cnic")
    inlines = [EducationInline, ExperienceInline, SkillInline]
