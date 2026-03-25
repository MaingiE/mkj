import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mkj_cms.settings')
django.setup()
from competitions.models import Competition
updated = Competition.objects.filter(season='2026', name__icontains='MKJ SUPA CUP').update(status='active')
print(f"Updated {updated} competitions to active status")
for c in Competition.objects.filter(season='2026').order_by('name'):
    print(f"  {c.name} -> status={c.status}")
