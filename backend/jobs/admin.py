from django.contrib import admin

from .models import (
    InternalJobApplication,
    InternalJobApplicationCertification,
    InternalJobApplicationEducation,
    InternalJobApplicationExperience,
    InternalJobApplicationTraining,
    JobDescription,
    JobRequisition,
)


@admin.register(JobDescription)
class JobDescriptionAdmin(admin.ModelAdmin):
    """The library of descriptions the vacancies point at."""

    list_display = ("title", "code", "department", "grade", "is_active", "updated_at")
    list_filter = ("is_active", "department", "grade")
    search_fields = ("title", "code", "department", "key_responsibilities")


@admin.register(JobRequisition)
class JobRequisitionAdmin(admin.ModelAdmin):
    """HR adds and closes vacancies here as well as from Job Openings.

    Closing a requisition removes it from the application form while leaving
    the applications already filed against it intact.
    """

    list_display = (
        "title", "reference_no", "grade", "department",
        "job_description", "advertisement_date", "closing_date", "is_open", "created_at",
    )
    list_filter = ("is_open", "department", "grade")
    search_fields = ("title", "reference_no", "department", "location")


class EducationInline(admin.TabularInline):
    model = InternalJobApplicationEducation
    extra = 0


class ExperienceInline(admin.TabularInline):
    model = InternalJobApplicationExperience
    extra = 0


class CertificationInline(admin.TabularInline):
    model = InternalJobApplicationCertification
    extra = 0


class TrainingInline(admin.TabularInline):
    model = InternalJobApplicationTraining
    extra = 0


@admin.register(InternalJobApplication)
class InternalJobApplicationAdmin(admin.ModelAdmin):
    """Read side of the review flow: one row per application, sections inline."""

    list_display = (
        "id", "application_reference_no", "full_name", "emp_id", "target_job_req",
        "department_function", "current_designation", "status", "created_at",
    )
    list_filter = ("status", "target_job_req", "current_grade")
    search_fields = (
        "full_name", "emp_id", "official_email", "cnic", "application_reference_no",
    )
    inlines = [EducationInline, ExperienceInline, CertificationInline, TrainingInline]
