from django.db import migrations


class Migration(migrations.Migration):
    """
    No-op migration: registration_deadline was already included in 0038_ligisettings.
    This migration was generated when the field was added directly to the local SQLite db,
    but the field already exists in the 0038 CreateModel operation.
    """

    dependencies = [
        ('teams', '0038_ligisettings'),
    ]

    operations = [
        # No operations needed - field already exists from migration 0038
    ]
