from django.db import models
from django.utils import timezone
# Create your models here.

class LeaveModel(models.Model):
    id= models.AutoField(primary_key=True)
    employee_id = models.IntegerField(default=0)
    erp_id = models.IntegerField(default=0)  # Assuming erp_id is an integer, adjust as necessary
    leave_type = models.CharField(max_length=50, null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    reason = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=20, default='Pending')  # e.g., Pending, Approved, Rejected
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'leaves'
