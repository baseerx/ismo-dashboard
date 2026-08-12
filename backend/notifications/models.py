from django.db import models
from django.utils import timezone


class Notification(models.Model):
    """An in-app notification addressed to one employee.

    Addressed by ERP ID rather than by a foreign key to auth_user, because
    every module in this project already identifies people by erp_id and the
    two are only loosely linked (see addtouser.CustomUser).

    `link` holds a frontend route, so the notification can carry the user
    straight to the page the activity concerns.
    """

    # Who should see it.
    recipient_erp_id = models.IntegerField(db_index=True)

    # Which module raised it: 'leave', 'official_work', ...
    category = models.CharField(max_length=40)

    # What happened: 'approved', 'rejected', 'awaiting_approval', ...
    event = models.CharField(max_length=40)

    title = models.CharField(max_length=150)
    message = models.TextField(null=True, blank=True)

    # Frontend route to open when the notification is clicked.
    link = models.CharField(max_length=255, null=True, blank=True)

    # Primary key of the row this is about (a leave id, official work id, ...),
    # kept so a notification can be traced back to its source record.
    related_id = models.IntegerField(null=True, blank=True)

    # ERP ID of whoever caused the activity, for "approved by" style text.
    actor_erp_id = models.IntegerField(null=True, blank=True)

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            # The unread badge query: recipient + unread, newest first.
            models.Index(
                fields=['recipient_erp_id', 'is_read'],
                name='notif_recipient_unread_idx',
            ),
        ]

    def __str__(self):
        return f"[{self.category}/{self.event}] -> {self.recipient_erp_id}"
