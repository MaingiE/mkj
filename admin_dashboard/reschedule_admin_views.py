# admin_dashboard/reschedule_admin_views.py - MKJ SUPA CUP CMS
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from competitions.models import Fixture, Competition


@staff_member_required
def reschedule_fixtures_admin(request):
    """Reschedule fixtures — lists all pending/postponed fixtures grouped by competition."""
    sport_filter = request.GET.get('sport', '')
    fixtures = Fixture.objects.filter(
        status__in=['pending', 'postponed', 'confirmed']
    ).select_related(
        'competition', 'home_team', 'away_team', 'venue'
    ).order_by('competition__sport_type', 'match_date')

    if sport_filter:
        fixtures = fixtures.filter(competition__sport_type=sport_filter)

    competitions = Competition.objects.filter(
        fixtures__status__in=['pending', 'postponed', 'confirmed']
    ).distinct().order_by('sport_type', 'name')

    return render(request, 'admin_dashboard/reschedule_fixtures.html', {
        'fixtures': fixtures,
        'competitions': competitions,
        'sport_filter': sport_filter,
    })
