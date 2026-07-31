from django.db import migrations, models


# The original 0001_initial declared `head_employee` as a ForeignKey to
# users.Employees, which made the DB create a FK constraint
# (sub_sections.head_employee_id -> employees.id). But the entire codebase
# (activities, businessplan, dashboard, subsections) treats head_employee_id as
# an employee's *erp_id*, not employees.id. That mismatch made every insert of a
# real erp_id fail with a FOREIGN KEY constraint violation (500 error).
#
# This migration converts the field to a plain BigIntegerField (matching the
# existing bigint column) and drops ONLY the FK constraint via
# SeparateDatabaseAndState, so the column and any data are left untouched. The
# DROP is written to look the constraint up by column, so it works regardless of
# the auto-generated constraint name across environments.

DROP_FK_SQL = """
DECLARE @c sysname;
SELECT @c = fk.name
FROM sys.foreign_keys fk
JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
JOIN sys.columns col ON col.object_id = fkc.parent_object_id
                     AND col.column_id = fkc.parent_column_id
WHERE fk.parent_object_id = OBJECT_ID('sub_sections')
  AND col.name = 'head_employee_id';
IF @c IS NOT NULL EXEC('ALTER TABLE sub_sections DROP CONSTRAINT ' + @c);
"""

# Best-effort reverse: re-create a FK constraint back to employees.id.
READD_FK_SQL = """
IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys fk
    JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    JOIN sys.columns col ON col.object_id = fkc.parent_object_id
                         AND col.column_id = fkc.parent_column_id
    WHERE fk.parent_object_id = OBJECT_ID('sub_sections')
      AND col.name = 'head_employee_id'
)
ALTER TABLE sub_sections
ADD CONSTRAINT sub_sections_head_employee_id_fk_employees_id
FOREIGN KEY (head_employee_id) REFERENCES employees (id);
"""


class Migration(migrations.Migration):

    dependencies = [
        ('subsections', '0001_initial'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(model_name='subsection', name='head_employee'),
                migrations.AddField(
                    model_name='subsection',
                    name='head_employee_id',
                    field=models.BigIntegerField(default=0),
                    preserve_default=False,
                ),
            ],
            database_operations=[
                migrations.RunSQL(sql=DROP_FK_SQL, reverse_sql=READD_FK_SQL),
            ],
        ),
    ]
