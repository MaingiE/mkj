from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('competitions', '0015_ligi_mashinani_pipeline_models'),
        ('teams', '0040_ligitransferrequest'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='WardSubstitutionRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('minute', models.PositiveIntegerField(help_text='Match minute')),
                ('status', models.CharField(
                    choices=[
                        ('requested', 'Requested'),
                        ('approved', 'Approved'),
                        ('executed', 'Executed'),
                        ('denied', 'Denied'),
                    ],
                    default='requested', max_length=12)),
                ('reason', models.TextField(blank=True, default='')),
                ('denial_reason', models.TextField(blank=True, default='')),
                ('requested_at', models.DateTimeField(auto_now_add=True)),
                ('decided_at', models.DateTimeField(blank=True, null=True)),
                ('fixture', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ward_substitution_requests',
                    to='competitions.fixture')),
                ('team', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ward_substitution_requests',
                    to='teams.team')),
                ('player_off', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ward_subbed_off',
                    to='teams.countyplayer')),
                ('player_on', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ward_subbed_on',
                    to='teams.countyplayer')),
                ('requested_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='ward_sub_requests_made',
                    to=settings.AUTH_USER_MODEL)),
                ('approved_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='ward_sub_requests_approved',
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Ward Substitution Request',
                'verbose_name_plural': 'Ward Substitution Requests',
                'ordering': ['fixture', 'minute'],
            },
        ),
    ]
