from django.db import models

class Attendance(models.Model):
    uid = models.IntegerField()
    user_id = models.IntegerField()
    timestamp = models.DateTimeField()
    status = models.CharField(max_length=250)
    punch = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'attendance'  # Use your actual table name
        # Remove unique_together if not present in the DB

    def __str__(self):
        return f"Attendance for User {self.user_id} at {self.timestamp}"
