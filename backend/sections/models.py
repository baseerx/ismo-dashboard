from django.db import models

# Create your models here.
class Sections(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = 'sections'