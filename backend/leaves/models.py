from django.db import models
from django.utils import timezone
# Create your models here.

class LeaveModel(models.Model):
    employee_id = models.IntegerField(default=0)
    erp_id = models.IntegerField(default=0)  # Assuming erp_id is an integer, adjust as necessary
    head_erpid = models.IntegerField(default=0)  # Assuming erp_id is an integer, adjust as necessary
    leave_type = models.CharField(max_length=50, null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    total_days = models.IntegerField(default=0)
    reason = models.TextField(null=True, blank=True)
    approved_by = models.TextField(null=True, blank=True)
    entry_made_by = models.IntegerField(default=0)
    status = models.CharField(max_length=20, default='pending')  # e.g., Pending, Approved, Rejected
    created_at = models.DateTimeField(default=timezone.now)

    # Supporting document for medical / sick leave. Stored under a generated
    # name rather than the uploaded one: these are medical records, and the
    # original filename often carries the patient's name.
    attachment = models.FileField(
        upload_to='leave_attachments/%Y/%m/',
        null=True,
        blank=True,
    )
    # The name the employee uploaded, kept for display only.
    attachment_original_name = models.CharField(
        max_length=255, null=True, blank=True
    )

    class Meta:
        db_table = 'leaves'

class LeaveTypeCountModel(models.Model):
    leave_type = models.CharField(max_length=50, null=True, blank=True)
    total_leaves = models.IntegerField(default=0)

    class Meta:
        db_table = 'leave_type_counts'