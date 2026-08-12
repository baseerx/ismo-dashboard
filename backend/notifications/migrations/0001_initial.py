from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('recipient_erp_id', models.IntegerField(db_index=True)),
                ('category', models.CharField(max_length=40)),
                ('event', models.CharField(max_length=40)),
                ('title', models.CharField(max_length=150)),
                ('message', models.TextField(blank=True, null=True)),
                ('link', models.CharField(blank=True, max_length=255, null=True)),
                ('related_id', models.IntegerField(blank=True, null=True)),
                ('actor_erp_id', models.IntegerField(blank=True, null=True)),
                ('is_read', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={
                'db_table': 'notifications',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['recipient_erp_id', 'is_read'],
                               name='notif_recipient_unread_idx'),
        ),
    ]
