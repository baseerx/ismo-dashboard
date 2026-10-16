from django.db import models



class Attendance(models.Model):
    uid = models.IntegerField()
    user_id = models.IntegerField()
    timestamp = models.DateTimeField()
    status = models.CharField(max_length=250)
    punch = models.IntegerField(null=True, blank=True)
    lateintime = models.CharField(max_length=250, null=True, blank=True)
    
    class Meta:
        db_table = 'attendance'


class AttendanceManualEdit(models.Model):
    """One manual change to an employee's check-in / check-out for a day.

    Written by the Update Attendance page (attendance/manual_entry.py) every
    time an administrator inserts or corrects a punch, so a corrected day can
    always be traced: who changed it, when, from what, to what, and why.
    """

    erp_id = models.IntegerField(db_index=True)
    hris_id = models.IntegerField()
    work_date = models.DateField(db_index=True)

    # "HH:MM", or "" when there was none / it was left alone.
    old_check_in = models.CharField(max_length=8, default="", blank=True)
    new_check_in = models.CharField(max_length=8, default="", blank=True)
    old_check_out = models.CharField(max_length=8, default="", blank=True)
    new_check_out = models.CharField(max_length=8, default="", blank=True)

    reason = models.CharField(max_length=300)
    # auth_user id of the administrator who made the change.
    changed_by = models.IntegerField()
    changed_by_name = models.CharField(max_length=150, default="", blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "attendance_manual_edits"
        ordering = ["-changed_at"]

