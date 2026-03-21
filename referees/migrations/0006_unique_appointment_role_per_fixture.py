from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("referees", "0005_expand_role_maxlen_add_optional_roles"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="refereeappointment",
            constraint=models.UniqueConstraint(
                fields=("fixture", "role"),
                name="unique_appointment_role_per_fixture",
            ),
        ),
    ]