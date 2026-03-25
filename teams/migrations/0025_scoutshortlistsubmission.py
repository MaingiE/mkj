from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('teams', '0024_alter_countydiscipline_sport_type_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScoutShortlistSubmission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('submitted', 'Final List Submitted'), ('edit_requested', 'Edit Access Requested'), ('edit_approved', 'Edit Access Approved'), ('edit_denied', 'Edit Access Denied')], default='draft', max_length=20)),
                ('final_submitted_at', models.DateTimeField(blank=True, null=True)),
                ('edit_requested_at', models.DateTimeField(blank=True, null=True)),
                ('edit_request_reason', models.TextField(blank=True, default='')),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('review_notes', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='scout_shortlist_reviews', to=settings.AUTH_USER_MODEL)),
                ('scout', models.OneToOneField(limit_choices_to={'role': 'scout'}, on_delete=django.db.models.deletion.CASCADE, related_name='scout_shortlist_submission', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-updated_at'],
                'verbose_name': 'Scout Shortlist Submission',
                'verbose_name_plural': 'Scout Shortlist Submissions',
            },
        ),
    ]