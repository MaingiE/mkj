import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mkj_cms.settings')
import django; django.setup()
from competitions.models import Fixture, KnockoutRound
semis = Fixture.objects.filter(is_knockout=True, knockout_round=KnockoutRound.SEMIFINAL)
sys.stdout.write(f'Semi-finals count: {semis.count()}\n')
for f in semis:
    sys.stdout.write(f'  {f.competition.sport_type}: {f.home_team} vs {f.away_team} [{f.status}]\n')
sys.stdout.flush()
