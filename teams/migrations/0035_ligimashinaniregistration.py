from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('teams', '0034_bulk_upload_coordinator_approval'),
    ]

    operations = [
        migrations.CreateModel(
            name='LigiMashinaniRegistration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sub_county', models.CharField(max_length=100, help_text='Makueni sub-county')),
                ('ward', models.CharField(max_length=100, help_text='Ward within the sub-county')),
                ('team_name', models.CharField(max_length=200, help_text='Ward/Ligi Mashinani team name')),
                ('discipline', models.CharField(
                    max_length=30,
                    choices=[
                        ('football_men', 'Soccer (Men)'),
                        ('football_women', 'Soccer (Women)'),
                        ('volleyball_men', 'Volleyball (Men)'),
                        ('volleyball_women', 'Volleyball (Women)'),
                        ('basketball_men', 'Basketball 5x5 (Men)'),
                        ('basketball_women', 'Basketball 5x5 (Women)'),
                        ('basketball_3x3_men', 'Basketball 3x3 (Men)'),
                        ('basketball_3x3_women', 'Basketball 3x3 (Women)'),
                        ('handball_men', 'Handball (Men)'),
                        ('handball_women', 'Handball (Women)'),
                    ],
                    help_text='Sport discipline',
                )),
                ('manager_first_name', models.CharField(max_length=100, help_text='Team manager first name')),
                ('manager_last_name', models.CharField(max_length=100, help_text='Team manager last name')),
                ('manager_email', models.EmailField(unique=True, help_text='Team manager email address')),
                ('manager_phone', models.CharField(max_length=13, help_text='WhatsApp-enabled phone number')),
                ('status', models.CharField(
                    max_length=20,
                    choices=[
                        ('pending', 'Pending Ward Verification'),
                        ('ward_verified', 'Ward Sports Council Verified'),
                        ('approved', 'System Admin Approved'),
                        ('rejected', 'Rejected'),
                    ],
                    default='pending',
                    help_text='Registration approval status',
                )),
                ('rejection_reason', models.TextField(blank=True, default='')),
                ('account_created', models.BooleanField(default=False, help_text='Portal account auto-created for team manager')),
                ('submitted_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('notes', models.TextField(blank=True, default='', help_text='Internal admin notes')),
            ],
            options={
                'verbose_name': 'Ligi Mashinani Registration',
                'verbose_name_plural': 'Ligi Mashinani Registrations',
                'ordering': ['-submitted_at'],
            },
        ),
    ]
