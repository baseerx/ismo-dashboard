from django.db import models
from django.utils import timezone
# Create your models here.

class LeaveModel(models.Model):
    employee_id = models.IntegerField(default=0)
    erp_id = models.IntegerField(default=0)  
    head_erpid = models.IntegerField(default=0) 
    leave_type = models.CharField(max_length=50, null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    total_days = models.IntegerField(default=0)
    reason = models.TextField(null=True, blank=True)
    approved_by = models.TextField(null=True, blank=True)
    entry_made_by = models.IntegerField(default=0)
    status = models.CharField(max_length=20, default='pending') 
    created_at = models.DateTimeField(default=timezone.now)

    attachment = models.FileField(
        upload_to='leave_attachments/%Y/%m/',
        null=True,
        blank=True,
    )
    
    attachment_original_name = models.CharField(
        max_length=255, null=True, blank=True
    )

  
    is_lwp_overflow = models.BooleanField(default=False)
    lwp_days = models.IntegerField(default=0)

    class Meta:
        db_table = 'leaves'

class LeaveTypeCountModel(models.Model):
    leave_type = models.CharField(max_length=50, null=True, blank=True)
    total_leaves = models.IntegerField(default=0)

    class Meta:
        db_table = 'leave_type_counts'



class LeaveApprovalStage(models.Model):

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("skipped", "Skipped"),  # e.g. a conditional stage that didn't apply
    ]

    leave = models.ForeignKey(
        LeaveModel, on_delete=models.CASCADE, related_name="approval_stages"
    )
    sequence = models.IntegerField()  # order within this leave's chain, 0-based
    label = models.CharField(max_length=100)   # e.g. "Recommended By"
    role_key = models.CharField(max_length=32)  # e.g. "reporting_officer"
    assigned_erp_id = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    acted_by_erp_id = models.IntegerField(null=True, blank=True)
    comment = models.TextField(null=True, blank=True)
    acted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'leave_approval_stages'
        ordering = ['leave_id', 'sequence']
        unique_together = [('leave', 'sequence')]        