# admin_dashboard/admin_views.py - MKJ SUPA CUP CMS
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.contrib import messages
from competitions.models import Competition, Fixture


@staff_member_required
def generate_fixtures_admin(request):
    """Generate fixtures for a competition (placeholder)."""
    competitions = Competition.objects.all().order_by('name')

    if request.method == 'POST':
        comp_id = request.POST.get('competition_id')
        if comp_id:
            messages.info(request, "Fixture generation coming soon.")
        return redirect('generate_fixtures_admin')

    return render(request, 'admin_dashboard/generate_fixtures.html', {
        'competitions': competitions,
    })
