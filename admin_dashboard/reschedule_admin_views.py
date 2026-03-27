# admin_dashboard/reschedule_admin_views.py - MKJ SUPA CUP CMS
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from competitions.models import Fixture


@staff_member_required
def reschedule_fixtures_admin(request):
    """Reschedule fixtures (placeholder)."""
    fixtures = Fixture.objects.filter(
        status__in=['scheduled', 'postponed']
    ).order_by('match_date')
    return render(request, 'admin_dashboard/reschedule_fixtures.html', {
        'fixtures': fixtures,
    })
