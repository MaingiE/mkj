from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('teams', '0045_player_reg_request'),
    ]

    operations = [
        migrations.AddField(
            model_name='ligisettings',
            name='team_reg_open_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='Auto-open team registration at this datetime (Nairobi time). Cleared once applied.',
            ),
        ),
        migrations.AddField(
            model_name='ligisettings',
            name='team_reg_close_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='Auto-close team registration at this datetime (Nairobi time). Cleared once applied.',
            ),
        ),
        migrations.AddField(
            model_name='ligisettings',
            name='player_reg_open_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='Auto-open player registration at this datetime (Nairobi time). Cleared once applied.',
            ),
        ),
        migrations.AddField(
            model_name='ligisettings',
            name='player_reg_close_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='Auto-close player registration at this datetime (Nairobi time). Cleared once applied.',
            ),
        ),
    ]
