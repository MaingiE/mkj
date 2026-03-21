from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("matches", "0004_matchreport_away_sets_matchreport_away_suspensions_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="matchreport",
            name="appointment_snapshot",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Snapshot of appointed officials for this fixture when the report was last saved.",
            ),
        ),
    ]