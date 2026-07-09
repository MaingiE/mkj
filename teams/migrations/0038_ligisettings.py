from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('teams', '0037_ligi_mashinani_pipeline_models'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LigiSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('team_registration_open', models.BooleanField(
                    default=True,
                    help_text='Allow new Ligi Mashinani team registrations on the public homepage.',
                )),
                ('team_registration_closed_message', models.CharField(
                    blank=True,
                    default='Team registration for Ligi Mashinani is currently closed.',
                    max_length=300,
                    help_text='Message shown to the public when team registration is closed.',
                )),
                ('player_registration_open', models.BooleanField(
                    default=True,
                    help_text='Allow Ward Team Managers to add players to their ward longlist.',
                )),
                ('player_registration_closed_message', models.CharField(
                    blank=True,
                    default='Player registration for Ligi Mashinani is currently closed.',
                    max_length=300,
                    help_text='Message shown to Ward TM when player registration is closed.',
                )),
                ('transfer_window_open', models.BooleanField(
                    default=False,
                    help_text='Allow player transfers between ward teams during the transfer window.',
                )),
                ('transfer_window_closed_message', models.CharField(
                    blank=True,
                    default='The Ligi Mashinani transfer window is currently closed.',
                    max_length=300,
                    help_text='Message shown to Ward TM when the transfer window is closed.',
                )),
                ('registration_deadline', models.DateTimeField(
                    null=True, blank=True,
                    help_text='Optional deadline datetime for team registration. Shown as a live countdown on the public homepage.',
                )),
                ('last_changed_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='ligi_settings_changes',
                    to=settings.AUTH_USER_MODEL,
                    help_text='Last user to change these settings.',
                )),
                ('last_changed_at', models.DateTimeField(null=True, blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Ligi Mashinani Settings',
                'verbose_name_plural': 'Ligi Mashinani Settings',
            },
        ),
    ]
