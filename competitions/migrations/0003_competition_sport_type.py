from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('competitions', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='competition',
            name='sport_type',
            field=models.CharField(
                max_length=30,
                choices=[
                    ('soccer',           'Soccer'),
                    ('volleyball_men',   'Volleyball (Men)'),
                    ('volleyball_women', 'Volleyball (Women)'),
                    ('basketball',       'Basketball'),
                    ('basketball_3x3',   'Basketball 3x3'),
                    ('handball',         'Handball'),
                    ('beach_volleyball', 'Beach Volleyball'),
                    ('beach_handball',   'Beach Handball'),
                ],
                default='soccer',
                help_text='Sport discipline for this competition',
            ),
        ),
        migrations.AddField(
            model_name='competition',
            name='is_exhibition',
            field=models.BooleanField(
                default=False,
                help_text='Mark as exhibition match (e.g. Beach Volleyball, Beach Handball)',
            ),
        ),
    ]
