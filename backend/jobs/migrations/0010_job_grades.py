"""Internal Hiring's own grade list, `job_grades`, seeded with MG-01 .. MG-10.

Advertised posts are graded on the MG scale, which the employees' `grades`
table (G-01 .. G-11, Internee) does not hold. Kept in a table of its own so
Attendance, Leaves and the section-head rules, which rank people by `grades`,
are not affected. Additive: a new table and its rows.
"""

from django.db import migrations, models


MG_GRADES = [f"MG-{level:02d}" for level in range(1, 11)]


def seed_grades(apps, schema_editor):
    JobGrade = apps.get_model("jobs", "JobGrade")
    for rank, name in enumerate(MG_GRADES, start=1):
        JobGrade.objects.update_or_create(name=name, defaults={"rank": rank})


def unseed_grades(apps, schema_editor):
    apps.get_model("jobs", "JobGrade").objects.filter(name__in=MG_GRADES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0009_record_mismatches'),
    ]

    operations = [
        migrations.CreateModel(
            name='JobGrade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=40, unique=True)),
                ('rank', models.IntegerField(default=0)),
            ],
            options={
                'db_table': 'job_grades',
                'ordering': ['rank', 'name'],
            },
        ),
        migrations.RunPython(seed_grades, unseed_grades),
    ]
