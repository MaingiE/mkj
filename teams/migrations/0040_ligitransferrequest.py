from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('teams', '0039_ligisettings_add_deadline'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LigiTransferRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('reason', models.TextField(
                    help_text='Reason for transfer request (required)')),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending WSCC Review'),
                        ('wscc_approved', 'WSCC Approved — Pending SCSO'),
                        ('wscc_rejected', 'Rejected by WSCC'),
                        ('scso_approved', 'Approved — Transfer Complete'),
                        ('scso_rejected', 'Rejected by Sub-County Officer'),
                        ('withdrawn', 'Withdrawn by Team Manager'),
                    ],
                    default='pending', max_length=20)),
                ('wscc_notes', models.TextField(blank=True, default='')),
                ('wscc_reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('scso_notes', models.TextField(blank=True, default='')),
                ('scso_reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('requested_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('player', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='transfer_requests',
                    to='teams.countyplayer')),
                ('from_discipline', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='outgoing_transfers',
                    to='teams.countydiscipline')),
                ('to_discipline', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='incoming_transfers',
                    to='teams.countydiscipline')),
                ('requested_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='transfer_requests_made',
                    to=settings.AUTH_USER_MODEL)),
                ('wscc_reviewed_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='wscc_transfer_reviews',
                    to=settings.AUTH_USER_MODEL)),
                ('scso_reviewed_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='scso_transfer_reviews',
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Ligi Transfer Request',
                'verbose_name_plural': 'Ligi Transfer Requests',
                'ordering': ['-requested_at'],
            },
        ),
    ]
