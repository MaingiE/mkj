from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Team
from .forms_edit import TeamEditForm

def league_admin_or_manager(user):
    return user.is_staff or user.groups.filter(name__in=['League Admin', 'League Manager']).exists()

@login_required
@user_passes_test(league_admin_or_manager)
def edit_team_info(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    if request.method == 'POST':
        form = TeamEditForm(request.POST, request.FILES, instance=team)
        if form.is_valid():
            form.save()
            messages.success(request, '✅ Team info updated successfully.')
            return redirect('teams:team_detail', team_id=team.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = TeamEditForm(instance=team)
    return render(request, 'teams/edit_team_info.html', {'form': form, 'team': team})
