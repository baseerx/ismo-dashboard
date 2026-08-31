"""Reshapes the application tables to the printed ISMO form.

The old layout came from a draft specification; this one follows the official
"Internal Recruitment - Online Application Form" section by section. Columns
that the form does not ask for are dropped, the repeating tables are rebuilt
with the printed column names, and two new repeating tables are added for
certifications and trainings.

Applications submitted under the old layout are removed first: most of their
columns no longer exist, so keeping the rows would leave records that cannot be
printed or reviewed. This runs while only test submissions exist.
"""

import django.db.models.deletion
from django.db import migrations, models


def clear_old_submissions(apps, schema_editor):
    """Empty the application tables before their columns change."""
    for table in (
        "internal_job_application_skills",
        "internal_job_application_education",
        "internal_job_application_experience",
        "internal_job_applications",
    ):
        schema_editor.execute(f"DELETE FROM {table}")


class Migration(migrations.Migration):

    dependencies = [
        ('jobs', '0002_internaljobapplication_ack_data_accuracy_bool_and_more'),
    ]

    operations = [
        migrations.RunPython(clear_old_submissions, migrations.RunPython.noop),

        # ---- 1. vacancy information the advertisement carries -------------
        migrations.AddField(
            model_name='jobrequisition',
            name='reference_no',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='jobrequisition',
            name='grade',
            field=models.CharField(blank=True, max_length=40, null=True),
        ),
        migrations.AddField(
            model_name='jobrequisition',
            name='advertisement_date',
            field=models.DateField(blank=True, null=True),
        ),

        # ---- the old application columns ----------------------------------
        migrations.RemoveField(model_name='internaljobapplication', name='emp_full_name'),
        migrations.RemoveField(model_name='internaljobapplication', name='current_dept_code'),
        migrations.RemoveField(model_name='internaljobapplication', name='current_job_title'),
        migrations.RemoveField(model_name='internaljobapplication', name='current_supervisor_id'),
        migrations.RemoveField(model_name='internaljobapplication', name='current_supervisor_erp_id'),
        migrations.RemoveField(model_name='internaljobapplication', name='contact_phone_no'),
        migrations.RemoveField(model_name='internaljobapplication', name='corporate_email'),
        migrations.RemoveField(model_name='internaljobapplication', name='personal_email'),
        migrations.RemoveField(model_name='internaljobapplication', name='preferred_contact_method'),
        migrations.RemoveField(model_name='internaljobapplication', name='certifications_list'),
        migrations.RemoveField(model_name='internaljobapplication', name='application_rationale_sop'),
        migrations.RemoveField(model_name='internaljobapplication', name='ack_manager_notified_bool'),
        migrations.RemoveField(model_name='internaljobapplication', name='ack_data_accuracy_bool'),

        # ---- 1. vacancy information, as submitted -------------------------
        migrations.AddField(
            model_name='internaljobapplication',
            name='vacancy_position_title',
            field=models.CharField(default='', max_length=200),
        ),
        migrations.AddField(
            model_name='internaljobapplication',
            name='vacancy_reference_no',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='internaljobapplication',
            name='vacancy_grade',
            field=models.CharField(blank=True, max_length=40, null=True),
        ),
        migrations.AddField(
            model_name='internaljobapplication',
            name='vacancy_department',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='internaljobapplication',
            name='vacancy_advertisement_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='internaljobapplication',
            name='vacancy_closing_date',
            field=models.DateField(blank=True, null=True),
        ),

        # ---- 2. personal & contact information ----------------------------
        migrations.AddField(
            model_name='internaljobapplication',
            name='full_name',
            field=models.CharField(default='', max_length=150),
        ),
        migrations.AddField(
            model_name='internaljobapplication',
            name='father_or_husband_name',
            field=models.CharField(default='', max_length=150),
        ),
        migrations.AddField(
            model_name='internaljobapplication',
            name='date_of_birth',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='internaljobapplication',
            name='gender',
            field=models.CharField(default='', max_length=10),
        ),
        migrations.AddField(
            model_name='internaljobapplication',
            name='official_email',
            field=models.EmailField(default='', max_length=150),
        ),
        migrations.AddField(
            model_name='internaljobapplication',
            name='mobile_no',
            field=models.CharField(default='', max_length=25),
        ),
        migrations.AddField(
            model_name='internaljobapplication',
            name='current_office_location',
            field=models.CharField(default='', max_length=200),
        ),
        migrations.AddField(
            model_name='internaljobapplication',
            name='emergency_contact_no',
            field=models.CharField(blank=True, max_length=25, null=True),
        ),

        # ---- 3. current employment details --------------------------------
        migrations.AddField(
            model_name='internaljobapplication',
            name='date_of_joining_ismo',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='internaljobapplication',
            name='current_designation',
            field=models.CharField(default='', max_length=200),
        ),
        migrations.AddField(
            model_name='internaljobapplication',
            name='current_grade',
            field=models.CharField(default='', max_length=40),
        ),
        migrations.AddField(
            model_name='internaljobapplication',
            name='department_function',
            field=models.CharField(default='', max_length=200),
        ),
        migrations.AddField(
            model_name='internaljobapplication',
            name='date_of_appointment_to_current_grade',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='internaljobapplication',
            name='total_service_ismo',
            field=models.CharField(default='', max_length=60),
        ),
        migrations.AddField(
            model_name='internaljobapplication',
            name='total_relevant_experience',
            field=models.CharField(default='', max_length=60),
        ),
        migrations.AddField(
            model_name='internaljobapplication',
            name='date_of_joining_current_position',
            field=models.DateField(blank=True, null=True),
        ),

        # ---- 8. declaration, 9. submission record -------------------------
        migrations.AddField(
            model_name='internaljobapplication',
            name='declaration_accepted',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='internaljobapplication',
            name='applicant_signature',
            field=models.CharField(default='', max_length=150),
        ),
        migrations.AddField(
            model_name='internaljobapplication',
            name='application_reference_no',
            field=models.CharField(blank=True, db_index=True, max_length=40, null=True),
        ),
        migrations.AddConstraint(
            model_name='internaljobapplication',
            constraint=models.UniqueConstraint(
                fields=('applicant_erp_id', 'target_job_req'),
                name='one_application_per_vacancy',
            ),
        ),

        # ---- 4 & 5: the repeating tables, rebuilt with printed names ------
        migrations.DeleteModel(name='InternalJobApplicationSkill'),
        migrations.DeleteModel(name='InternalJobApplicationEducation'),
        migrations.DeleteModel(name='InternalJobApplicationExperience'),

        migrations.CreateModel(
            name='InternalJobApplicationEducation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('degree_qualification', models.CharField(max_length=200)),
                ('major_field_of_study', models.CharField(max_length=200)),
                ('institution_university', models.CharField(max_length=200)),
                ('country', models.CharField(max_length=100)),
                ('year_of_completion', models.IntegerField()),
                ('cgpa_division', models.CharField(max_length=40)),
                ('row_order', models.IntegerField(default=0)),
                ('application', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='education', to='jobs.internaljobapplication')),
            ],
            options={
                'db_table': 'internal_job_application_education',
                'ordering': ['row_order', 'id'],
            },
        ),
        migrations.CreateModel(
            name='InternalJobApplicationExperience',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('organization_employer', models.CharField(max_length=200)),
                ('designation', models.CharField(max_length=200)),
                ('grade', models.CharField(blank=True, max_length=40, null=True)),
                ('from_date', models.DateField()),
                ('to_date', models.DateField(blank=True, null=True)),
                ('is_current', models.BooleanField(default=False)),
                ('duration', models.CharField(default='', max_length=60)),
                ('key_responsibilities', models.TextField()),
                ('row_order', models.IntegerField(default=0)),
                ('application', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='experience', to='jobs.internaljobapplication')),
            ],
            options={
                'db_table': 'internal_job_application_experience',
                'ordering': ['row_order', 'id'],
            },
        ),

        # ---- 6 & 7: new repeating tables ----------------------------------
        migrations.CreateModel(
            name='InternalJobApplicationCertification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('certification_membership', models.CharField(max_length=200)),
                ('certifying_body', models.CharField(max_length=200)),
                ('date_obtained', models.DateField(blank=True, null=True)),
                ('expiry_date', models.DateField(blank=True, null=True)),
                ('registration_no', models.CharField(blank=True, max_length=100, null=True)),
                ('row_order', models.IntegerField(default=0)),
                ('application', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='certifications', to='jobs.internaljobapplication')),
            ],
            options={
                'db_table': 'internal_job_application_certifications',
                'ordering': ['row_order', 'id'],
            },
        ),
        migrations.CreateModel(
            name='InternalJobApplicationTraining',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('training_title', models.CharField(max_length=200)),
                ('training_provider', models.CharField(max_length=200)),
                ('duration', models.CharField(blank=True, max_length=60, null=True)),
                ('date_or_year', models.CharField(blank=True, max_length=40, null=True)),
                ('relevant_to_position', models.BooleanField(default=False)),
                ('row_order', models.IntegerField(default=0)),
                ('application', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='trainings', to='jobs.internaljobapplication')),
            ],
            options={
                'db_table': 'internal_job_application_trainings',
                'ordering': ['row_order', 'id'],
            },
        ),
    ]
