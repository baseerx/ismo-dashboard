"""Adds the medical-record attachment columns to `leaves`.

Both columns are nullable with no default, so this is additive: existing rows
are untouched and older code that does not know about the fields keeps working.
Reversing the migration drops the columns (and therefore the references to any
uploaded files — the files themselves stay on disk under MEDIA_ROOT).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leaves', '0007_alter_leavemodel_entry_made_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='leavemodel',
            name='attachment',
            field=models.FileField(
                blank=True,
                null=True,
                upload_to='leave_attachments/%Y/%m/',
            ),
        ),
        migrations.AddField(
            model_name='leavemodel',
            name='attachment_original_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
