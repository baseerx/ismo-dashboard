from django.db import models

class Holiday(models.Model):
    id= models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    date = models.DateField()
    description = models.TextField(blank=True, null=True)


    class Meta:
        db_table = 'public_holidays'