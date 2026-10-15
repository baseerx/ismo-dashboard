from django.db import models


class Employees(models.Model):
    # assuming it's an auto-increment primary key

    erp_id = models.IntegerField()
    hris_id = models.IntegerField()
    name = models.CharField(max_length=100)
    cnic = models.CharField(max_length=15)
    gender = models.CharField(max_length=1)
    section_id = models.IntegerField()
    location_id = models.IntegerField()
    grade_id = models.IntegerField()
    designation_id = models.IntegerField()
    position = models.CharField(max_length=100)
    flag=models.IntegerField(default=0)
    # Empty for everyone already on file - it was never collected before, and
    # is filled in from Add Employee one record at a time.
    dob = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'employees'
        managed=True
        
class Users(models.Model):
    uid = models.AutoField(primary_key=True)
    user_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=100)
    privilege = models.IntegerField()
    password = models.CharField(max_length=100)
    group_id = models.IntegerField(null=True, blank=True)
    card = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = 'users'


class AccountLockout(models.Model):
    """Failed sign-ins for one account, and whether it is locked.

    Three wrong passwords in a row lock the account (MAX_FAILED_ATTEMPTS in
    users/lockout.py); an administrator can also lock one by hand. A locked
    account stays locked until an administrator unlocks it from Create User.
    Kept apart from auth_user.is_active, which already means something else on
    that screen.
    """

    user = models.OneToOneField(
        "auth.User", on_delete=models.CASCADE, related_name="lockout"
    )
    failed_attempts = models.IntegerField(default=0)
    last_failed_at = models.DateTimeField(null=True, blank=True)

    is_locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)
    # "3 failed sign-in attempts", or the administrator's own reason.
    locked_reason = models.CharField(max_length=200, default="", blank=True)
    # auth_user id of the administrator who locked it; null when it locked itself.
    locked_by = models.IntegerField(null=True, blank=True)

    unlocked_at = models.DateTimeField(null=True, blank=True)
    unlocked_by = models.IntegerField(null=True, blank=True)

    # Set when an administrator resets the password: on the next sign-in the
    # user must confirm their email and choose their own password before
    # anything else (users/lockout.py, ProtectedRoute on the frontend).
    must_change_password = models.BooleanField(default=False)

    class Meta:
        db_table = "account_lockouts"

    def __str__(self):
        return f"{self.user_id} locked={self.is_locked} failed={self.failed_attempts}"
