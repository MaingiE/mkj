"""
Migration: 0047_subcounty_finals_models

Adds all data model changes needed for the MKJ Supa Cup Subcounty Finals feature:
  - WardAllStarsTeam
  - OutsideLigiPlayerRequest + OutsideLigiRequestStatus
  - SubcountyDisciplineCoordinator
  - Team.qualified_to_subcounty_finals + qualifying_subcounty_competition FK
  - CountyPlayer.allstars_team FK + is_outside_ligi + outside_ligi_request FK
"""
import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('teams', '0046_ligisettings_scheduled_windows'),
        ('competitions', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        # ── WardAllStarsTeam ──────────────────────────────────────────────────
        migrations.CreateModel(
            name='WardAllStarsTeam',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ward', models.CharField(max_length=100)),
                ('sub_county', models.CharField(max_length=100)),
                ('sport_type', models.CharField(max_length=30)),
                ('official_name', models.CharField(help_text="Official name e.g. 'Mavindini Ward All Stars'", max_length=200)),
                ('appointed_coach_name', models.CharField(blank=True, default='', max_length=200)),
                ('appointed_at', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('qualified_from_ligi', models.BooleanField(default=False, help_text='True when ward champion flag is confirmed.')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('competition', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ward_all_stars_teams', to='competitions.competition')),
                ('appointed_by_wscc', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='wscc_allstars_appointments', to=settings.AUTH_USER_MODEL)),
                ('appointed_coach_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='coached_ward_allstars', to=settings.AUTH_USER_MODEL)),
                ('appointed_tm_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='managed_ward_allstars', to=settings.AUTH_USER_MODEL)),
                ('source_discipline', models.ForeignKey(blank=True, limit_choices_to={'level': 'ward'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='allstars_source', to='teams.countydiscipline')),
                ('subcounty_discipline', models.ForeignKey(blank=True, limit_choices_to={'level': 'subcounty'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ward_allstars_sources', to='teams.countydiscipline')),
            ],
            options={
                'verbose_name': 'Ward All Stars Team',
                'verbose_name_plural': 'Ward All Stars Teams',
                'ordering': ['sub_county', 'ward', 'sport_type'],
                'unique_together': {('competition', 'ward', 'sport_type')},
            },
        ),

        # ── OutsideLigiPlayerRequest ──────────────────────────────────────────
        migrations.CreateModel(
            name='OutsideLigiPlayerRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('player_name', models.CharField(max_length=200)),
                ('national_id', models.CharField(max_length=20, validators=[django.core.validators.RegexValidator(message='ID number must contain 5 to 10 digits.', regex='^\\d{5,10}$')])),
                ('date_of_birth', models.DateField()),
                ('justification', models.TextField(help_text='Why this player is needed and why they were not in Ligi Mashinani.')),
                ('supporting_doc', models.FileField(blank=True, null=True, upload_to='outside_ligi_requests/')),
                ('status', models.CharField(choices=[('pending_director', 'Pending Director of Sports'), ('forwarded_cso', 'Forwarded to Chief Sports Officer'), ('cso_approved', 'Approved by CSO'), ('cso_rejected', 'Rejected by CSO'), ('director_rejected', 'Rejected by Director of Sports')], db_index=True, default='pending_director', max_length=25)),
                ('director_reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('director_notes', models.TextField(blank=True, default='')),
                ('cso_reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('cso_notes', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('ward_allstars', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='outside_ligi_requests', to='teams.wardallstarsteam')),
                ('requested_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='outside_ligi_requests_made', to=settings.AUTH_USER_MODEL)),
                ('director_reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='director_olp_reviews', to=settings.AUTH_USER_MODEL)),
                ('cso_reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cso_olp_reviews', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Outside-Ligi Player Request',
                'verbose_name_plural': 'Outside-Ligi Player Requests',
                'ordering': ['-created_at'],
                'unique_together': {('ward_allstars', 'national_id')},
            },
        ),

        # ── SubcountyDisciplineCoordinator ────────────────────────────────────
        migrations.CreateModel(
            name='SubcountyDisciplineCoordinator',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sub_county', models.CharField(max_length=100)),
                ('sport_type', models.CharField(max_length=30)),
                ('season', models.CharField(default='2026', max_length=10)),
                ('appointed_at', models.DateTimeField(auto_now_add=True)),
                ('is_active', models.BooleanField(default=True)),
                ('user', models.ForeignKey(limit_choices_to={'role': 'coordinator'}, on_delete=django.db.models.deletion.CASCADE, related_name='sdc_assignments', to=settings.AUTH_USER_MODEL)),
                ('appointed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sdc_appointments_made', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Subcounty Discipline Coordinator',
                'verbose_name_plural': 'Subcounty Discipline Coordinators',
                'unique_together': {('sub_county', 'sport_type', 'season')},
            },
        ),

        # ── Team model extensions ─────────────────────────────────────────────
        migrations.AddField(
            model_name='team',
            name='qualified_to_subcounty_finals',
            field=models.BooleanField(default=False, help_text='True when this ward team qualifies to MKJ Supa Cup Subcounty Finals'),
        ),
        migrations.AddField(
            model_name='team',
            name='qualifying_subcounty_competition',
            field=models.ForeignKey(blank=True, help_text='Subcounty Finals competition this ward team qualified for', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ward_qualified_teams', to='competitions.competition'),
        ),

        # ── CountyPlayer model extensions ─────────────────────────────────────
        migrations.AddField(
            model_name='countyplayer',
            name='allstars_team',
            field=models.ForeignKey(blank=True, help_text='Ward All Stars team this player is registered for (Subcounty Finals)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='allstars_players', to='teams.wardallstarsteam'),
        ),
        migrations.AddField(
            model_name='countyplayer',
            name='is_outside_ligi',
            field=models.BooleanField(default=False, help_text='True when player was not in Ligi Mashinani and added via OutsideLigiPlayerRequest'),
        ),
        migrations.AddField(
            model_name='countyplayer',
            name='outside_ligi_request',
            field=models.ForeignKey(blank=True, help_text="The approved OutsideLigiPlayerRequest that authorised this player's inclusion", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_players', to='teams.outsideligiplayerrequest'),
        ),
    ]
