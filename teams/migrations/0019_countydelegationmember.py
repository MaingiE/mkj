from django.conf import settings
from django.core.validators import RegexValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("teams", "0018_add_payment_method_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CountyDelegationMember",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("cecm_sports", "CECM - Sports"),
                            ("chief_officer_sports", "Chief Officer - Sports"),
                            ("county_secretary", "County Secretary"),
                            ("county_attorney", "County Attorney"),
                            ("county_protocol", "County Protocol Officer"),
                            ("county_liaison", "County Liaison Officer"),
                            ("county_media", "County Media Officer"),
                            ("county_medical", "County Medical Officer"),
                            ("other", "Other"),
                        ],
                        max_length=40,
                    ),
                ),
                ("full_name", models.CharField(max_length=200)),
                (
                    "phone",
                    models.CharField(
                        max_length=13,
                        validators=[
                            RegexValidator(
                                message="Phone number must be in the format +254XXXXXXXXX (country code + 9 digits).",
                                regex="^\\+254\\d{9}$",
                            )
                        ],
                    ),
                ),
                ("national_id_number", models.CharField(max_length=20)),
                ("email", models.EmailField(blank=True, default="", max_length=254)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "registration",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="delegation_members", to="teams.countyregistration"),
                ),
                (
                    "user",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="county_delegation_profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["registration", "role", "full_name"],
                "unique_together": {("registration", "national_id_number")},
            },
        ),
    ]
