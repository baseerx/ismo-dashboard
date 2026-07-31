from django.db import models
from django.utils import timezone


class SubSection(models.Model):
    sub_section_name = models.CharField(max_length=150)
    section          = models.ForeignKey(
                         'sections.Sections',
                         on_delete=models.CASCADE,
                         db_column='section_id',
                         related_name='sub_sections',
                       )
    # NOTE: this stores an employee's erp_id, NOT a FK to employees.id.
    # The whole system (activities, businessplan, dashboard, subsections)
    # queries this column as head_employee_id == erp_id, so it must be a plain
    # integer column with NO DB-level FK constraint to employees.id — otherwise
    # inserting an erp_id (which is not a valid employees.id) is rejected.
    head_employee_id = models.BigIntegerField()
    created_at       = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'sub_sections'
        ordering = ['-created_at']

    def __str__(self):
        return self.sub_section_name
