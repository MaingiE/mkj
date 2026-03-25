import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mkj_cms.settings')
django.setup()
from competitions.models import Competition
for c in Competition.objects.all().order_by('season', 'name'):
    print(f"  id={c.pk} season={c.season} status={c.status} sport={c.sport_type} name={c.name}")
print(f"Total: {Competition.objects.count()}")
