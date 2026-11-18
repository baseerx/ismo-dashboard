"""Adds the short leave start and end time columns to `leaves`.

Both columns are nullable with no default, so this is additive: existing rows
are untouched and older code that does not know about the fields keeps working.
Only short leave fills them in.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leaves', '0008_leavemodel_attachment'),
    ]

    operations = [
        migrations.AddField(
            model_name='leavemodel',
            name='start_time',
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='leavemodel',
            name='end_time',
            field=models.TimeField(blank=True, null=True),
        ),
    ]
