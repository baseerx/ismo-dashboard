from django.db import models

# Create your models here.
class Users(models.Model):
    uid = models.IntegerField()
    user_id = models.IntegerField()
    name = models.CharField(max_length=250)
    privilege = models.CharField(max_length=250)
    password = models.CharField(max_length=150)
    group_id = models.CharField(max_length=250, null=True, blank=True)
    card = models.CharField(max_length=250, null=True, blank=True)

    class Meta:
        db_table = 'users'  # Use your actual table name
