from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('teams', '0001_initial'),
        ('competitions', '0003_competition_sport_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='team',
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
                help_text='Sport this team competes in',
            ),
        ),
    ]
