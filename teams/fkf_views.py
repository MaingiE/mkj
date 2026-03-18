from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from django.db import models
from django.urls import reverse
from .models import Team, Player, Zone, LeagueSettings, TransferRequest, TeamOfficial
from .forms import TeamRegistrationForm, PlayerRegistrationForm, TeamKitForm
from .officials_forms import TeamOfficialForm
from payments.models import Payment

def admin_or_league_manager_required(user):
    """Check if user is staff or in League Admin or League Manager group"""
    return user.is_staff or user.groups.filter(name__in=['League Admin', 'League Manager']).exists()

def team_registration(request):
    # Check if team registration is open
    settings = LeagueSettings.get_settings()
    if not settings.team_registration_open:
        return render(request, 'teams/registration_closed.html', {
            'title': 'Team Registration Closed',
            'message': 'Team registration is currently closed. Please check back later or contact the league administrator for more information.',
            'deadline': settings.team_registration_deadline
        })
    
    if request.method == 'POST':
        form = TeamRegistrationForm(request.POST, request.FILES)
        print(f"Form is valid: {form.is_valid()}")  # Debug
        if form.is_valid():
            try:
                team = form.save(commit=False)
                team.status = 'pending'
                
                # Generate team code if not already set in model save method
                if not team.team_code:
                    import uuid
                    team.team_code = str(uuid.uuid4())[:8].upper()
                
                team.save()
                print(f"Team saved: {team.team_name}, Code: {team.team_code}")  # Debug
                
                # Store in session for payment page
                request.session['registration_success'] = True
                request.session['success_team_name'] = team.team_name
                request.session['success_team_code'] = team.team_code
                request.session['team_id_for_payment'] = team.id
                
                # Add success message
                messages.success(request, 
                    f'✅ Team "{team.team_name}" registered successfully! '
                    f'Please proceed to payment.'
                )
                
                # REDIRECT to payment page
                return redirect('payments:payment_page', team_id=team.id)
                
            except Exception as e:
                print(f"Error saving team: {e}")  # Debug
                messages.error(request, f'Error saving team: {str(e)}')
        else:
            print(f"Form errors: {form.errors}")  # Debug
            for field, errors in form.errors.items():
                for error in errors:
                    if field == '__all__':
                        messages.error(request, f"{error}")
                    else:
                        messages.error(request, f"{field}: {error}")
    
    else:
        form = TeamRegistrationForm()
    
    return render(request, 'teams/register_improved.html', {'form': form, 'registration_fee': 16000})
def add_players(request):
    """Add players to team - Only accessible after approval"""
    # Check session for registration
    team_id = request.session.get('team_id')
    
    if not team_id:
        messages.error(request, 'Please register a team first!')
        return redirect('teams:team_registration')
    
    team = get_object_or_404(Team, id=team_id)
    
    # If user is logged in and this is not their team, check approval
    if request.user.is_authenticated and team.manager != request.user:
        if team.status != 'approved':
            messages.error(request, 'Your team is pending approval. You cannot add players yet.')
            return redirect('frontend:home')
    
    if request.method == 'POST':
        form = PlayerRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            player = form.save(commit=False)
            player.team = team
            
            # Check jersey number uniqueness
            if Player.objects.filter(team=team, jersey_number=player.jersey_number).exists():
                messages.error(request, f'Jersey number {player.jersey_number} is already taken.')
            else:
                # Check if ID number already exists
                if Player.objects.filter(id_number=player.id_number).exists():
                    messages.error(request, f'ID Number {player.id_number} is already registered.')
                else:
                    player.save()
                    messages.success(request, f'✅ Player {player.full_name} added successfully!')
                    
                    # FIXED: Check for 'action' parameter instead of button names
                    action = request.POST.get('action', 'add_more')
                    
                    if action == 'finish':
                        # Store team data in session BEFORE clearing
                        team_name = team.team_name
                        team_code = team.team_code
                        
                        # Clear session
                        if 'team_id' in request.session:
                            del request.session['team_id']
                        if 'team_code' in request.session:
                            del request.session['team_code']
                        
                        # Store in session for success page
                        request.session['registration_success'] = True
                        request.session['success_team_name'] = team_name
                        request.session['success_team_code'] = team_code
                        
                        # Add final success message
                        messages.success(request, 
                            f'🎉 REGISTRATION COMPLETE!<br>'
                            f'<strong>Team:</strong> {team_name}<br>'
                            f'<strong>Team Code:</strong> {team_code}<br>'
                            f'<strong>Status:</strong> Pending Approval<br>'
                            f'Admin will review and approve your registration.'
                        )
                        
                        return redirect('teams:registration_success')
                    else:
                        # Reset form for adding another player
                        form = PlayerRegistrationForm()
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PlayerRegistrationForm()
    
    players = Player.objects.filter(team=team).order_by('jersey_number')
    player_count = players.count()
    
    return render(request, 'teams/add_players.html', {
        'form': form,
        'team': team,
        'players': players,
        'player_count': player_count
    })

def registration_success(request):
    # Get data from session
    success = request.session.get('registration_success', False)
    team_name = request.session.get('success_team_name', '')
    team_code = request.session.get('success_team_code', '')
    
    # Clear session data
    if 'registration_success' in request.session:
        del request.session['registration_success']
    if 'success_team_name' in request.session:
        del request.session['success_team_name']
    if 'success_team_code' in request.session:
        del request.session['success_team_code']
    
    # If no success data, redirect to registration
    if not success:
        messages.info(request, 'Please complete team registration first.')
        return redirect('teams:team_registration')
    
    return render(request, 'teams/registration_success.html', {
        'team_name': team_name,
        'team_code': team_code,
        'success': success
    })

def team_dashboard(request, team_id=None):
    from matches.models import Match
    from referees.models import MatchdaySquad
    from tournaments.models import Tournament, TournamentTeamRegistration, ExternalTeam
    from django.utils import timezone
    from datetime import timedelta
    import logging
    
    logger = logging.getLogger(__name__)
    
    # If team_id is provided, show that team's dashboard
    if team_id:
        team = get_object_or_404(Team, id=team_id)
        logger.info(f"Team dashboard accessed via team_id: {team.team_name}")
    # If user is team manager, show their team's dashboard
    elif request.user.is_authenticated and hasattr(request.user, 'managed_teams'):
        team = request.user.managed_teams.first()
        if not team:
            messages.error(request, "You are not assigned to any team.")
            return redirect('dashboard')
        logger.info(f"Team dashboard accessed by manager: {request.user.username} for team: {team.team_name}")
    else:
        logger.warning(f"Team dashboard access attempt by user: {request.user} without team")
        messages.error(request, "Please specify a team.")
        return redirect('teams:all_teams')
    
    players = Player.objects.filter(team=team).order_by('jersey_number')
    payments = Payment.objects.filter(team=team) if hasattr(Payment, 'objects') else []
    
    # Get upcoming matches for this team
    today = timezone.now()
    upcoming_matches = Match.objects.filter(
        Q(home_team=team) | Q(away_team=team),
        match_date__gte=today.date(),
        status='scheduled'
    ).order_by('round_number', 'match_date', 'kickoff_time')[:5]
    
    logger.info(f"Found {upcoming_matches.count()} upcoming matches for team: {team.team_name}")
    
    # Find the current active round (most recent match that can be selected)
    current_round = None
    active_match = None
    
    if upcoming_matches.exists():
        # Get the first upcoming match's round
        first_match = upcoming_matches.first()
        current_round = first_match.round_number
        
        # Check if previous round is completed
        if current_round and current_round > 1:
            previous_round_matches = Match.objects.filter(
                Q(home_team=team) | Q(away_team=team),
                round_number=current_round - 1
            )
            
            # If previous round has any unplayed matches, block current round
            if previous_round_matches.filter(status='scheduled').exists():
                current_round = None  # Block squad submission
            else:
                active_match = first_match  # Only the first match in current round
        else:
            # First round or no round number, allow first match
            active_match = first_match
    
    # Prepare matches data with squad info
    matches_data = []
    for match in upcoming_matches:
        squad = MatchdaySquad.objects.filter(match=match, team=team).first()
        
        # Determine if this match can have squad submitted
        can_submit = False
        if active_match and match.id == active_match.id:
            # Check if within submission window (4 hours before kick-off) and not after kick-off
            try:
                if match.kickoff_time:
                    # Handle kickoff_time as string (CharField)
                    kickoff_time = match.kickoff_time
                    if isinstance(kickoff_time, str):
                        try:
                            kickoff_time = datetime.strptime(kickoff_time, '%H:%M:%S').time()
                        except (ValueError, AttributeError):
                            try:
                                kickoff_time = datetime.strptime(kickoff_time, '%H:%M').time()
                            except (ValueError, AttributeError):
                                kickoff_time = datetime.strptime('12:00', '%H:%M').time()  # Default to noon
                    
                    match_datetime = timezone.make_aware(
                        timezone.datetime.combine(match.match_date, kickoff_time)
                    )
                else:
                    # If no kickoff time, assume noon
                    match_datetime = timezone.make_aware(
                        timezone.datetime.combine(match.match_date, datetime.strptime('12:00', '%H:%M').time())
                    )
                time_until_match = match_datetime - today
                # Can submit if match hasn't started yet and within 4 hours window
                can_submit = time_until_match > timedelta(hours=0) and time_until_match <= timedelta(hours=4)
            except (ValueError, TypeError):
                # If date/time parsing fails, allow submission
                can_submit = True
        
        matches_data.append({
            'match': match,
            'squad': squad,
            'can_submit': can_submit,
            'is_active_match': active_match and match.id == active_match.id,
            'squad_status': squad.get_status_display() if squad else 'Not Submitted',
            'can_view_only': squad.can_view_only() if squad else False,
            'can_request_edit': squad.can_request_edit() if squad else False,
        })
    
    logger.info(f"Prepared {len(matches_data)} matches with squad info. Current round: {current_round}")
    logger.info(f"Active match: {active_match}")

    # ── Tournament data ─────────────────────────────────────────────────
    # Tournaments this league team is registered in
    team_tournament_regs = TournamentTeamRegistration.objects.filter(
        team=team
    ).select_related('tournament')

    # Tournaments the logged-in user's external teams are registered in
    external_tournament_regs = TournamentTeamRegistration.objects.none()
    if request.user.is_authenticated:
        ext_teams = ExternalTeam.objects.filter(manager_user=request.user)
        if ext_teams.exists():
            external_tournament_regs = TournamentTeamRegistration.objects.filter(
                external_team__in=ext_teams
            ).select_related('tournament', 'external_team')

    # Open tournaments the team can still register for
    open_tournaments = Tournament.objects.filter(
        status='registration',
        registration_deadline__gte=timezone.now(),
    ).exclude(
        registrations__team=team
    )

    return render(request, 'teams/dashboard.html', {
        'team': team,
        'players': players,
        'payments': payments,
        'upcoming_matches': matches_data,
        'current_round': current_round,
        'team_tournament_regs': team_tournament_regs,
        'external_tournament_regs': external_tournament_regs,
        'open_tournaments': open_tournaments,
    })

def all_teams(request):
    """View all teams - accessible to staff, superuser, League Admin, and League Manager"""
    if not request.user.is_authenticated:
        messages.error(request, "Please log in to access this page.")
        return redirect('login')

    if not (request.user.is_staff or request.user.is_superuser or request.user.groups.filter(name__in=['League Admin', 'League Manager']).exists()):
        messages.error(request, "You don't have permission to access this page.")
        return redirect('dashboard')

    teams = Team.objects.all()
    zones = Zone.objects.all()

    return render(request, 'teams/all_teams.html', {
        'teams': teams,
        'zones': zones
    })

def team_detail(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    players = Player.objects.filter(team=team).order_by('jersey_number')
    
    return render(request, 'teams/team_detail.html', {
        'team': team,
        'players': players
    })

def league_admin_dashboard(request):
    """Dashboard for league admin to manage all teams"""
    from django.utils import timezone
    from datetime import timedelta
    
    teams = Team.objects.all()
    recent_cutoff = timezone.now() - timedelta(days=7)
    
    context = {
        'teams_count': teams.count(),
        'active_teams': teams.filter(status='approved').count(),
        'pending_teams': teams.filter(status='pending').count(),
        'total_players': Player.objects.count(),
        'total_captains': Player.objects.filter(is_captain=True).count(),
        'paid_teams': teams.filter(payment_status=True).count(),
        'unpaid_teams': teams.filter(payment_status=False).count(),
        'recent_registrations': teams.filter(registration_date__gte=recent_cutoff).count(),
        'recent_teams': teams.order_by('-registration_date')[:10],
    }
    return render(request, 'teams/admin_dashboard.html', context)

@login_required
def update_team_kits(request, team_id=None):
    """Allow team managers to update their kit colors"""
    # If team_id provided and user is staff/admin, allow editing any team
    if team_id and request.user.is_staff:
        team = get_object_or_404(Team, id=team_id)
    # Otherwise, get the user's managed team
    elif request.user.is_authenticated and hasattr(request.user, 'managed_teams'):
        team = request.user.managed_teams.first()
        if not team:
            messages.error(request, "You are not assigned to any team.")
            return redirect('dashboard')
    else:
        messages.error(request, "You don't have permission to edit team kits.")
        return redirect('frontend:home')
    
    # Check if team is approved
    if team.status != 'approved' and not request.user.is_staff:
        messages.error(request, 'Your team must be approved before you can customize kits.')
        return redirect('teams:team_dashboard', team_id=team.id)
    
    if request.method == 'POST':
        form = TeamKitForm(request.POST, instance=team)
        if form.is_valid():
            team = form.save(commit=False)
            team.kit_colors_set = True  # mark as completed
            team.save()
            messages.success(request, '✅ Team kit colors updated successfully!')
            return redirect('teams:team_dashboard', team_id=team.id)
        else:
            for error in form.non_field_errors():
                messages.error(request, error)
    else:
        form = TeamKitForm(instance=team)
    
    return render(request, 'teams/select_kit.html', {
        'form': form,
        'team': team
    })

@login_required
def select_kit_colors(request):
    """Team manager selects kit colors AND images after approval"""
    # Get team managed by this user
    team = Team.objects.filter(manager=request.user, status='approved').first()
    
    if not team:
        messages.error(request, "You are not assigned to any approved team.")
        return redirect('dashboard')
    
    if request.method == 'POST':
        # Update all kit color fields from POST data
        team.home_jersey_color = request.POST.get('home_jersey_color', '#dc3545')
        team.home_shorts_color = request.POST.get('home_shorts_color', '#ffffff')
        team.home_socks_color = request.POST.get('home_socks_color', '#dc3545')
        
        team.away_jersey_color = request.POST.get('away_jersey_color', '#ffffff')
        team.away_shorts_color = request.POST.get('away_shorts_color', '#dc3545')
        team.away_socks_color = request.POST.get('away_socks_color', '#ffffff')
        
        team.third_jersey_color = request.POST.get('third_jersey_color', '')
        team.third_shorts_color = request.POST.get('third_shorts_color', '')
        team.third_socks_color = request.POST.get('third_socks_color', '')
        
        team.gk_home_jersey_color = request.POST.get('gk_home_jersey_color', '#28a745')
        team.gk_home_shorts_color = request.POST.get('gk_home_shorts_color', '#28a745')
        team.gk_home_socks_color = request.POST.get('gk_home_socks_color', '#28a745')
        
        team.gk_away_jersey_color = request.POST.get('gk_away_jersey_color', '#ffc107')
        team.gk_away_shorts_color = request.POST.get('gk_away_shorts_color', '#ffc107')
        team.gk_away_socks_color = request.POST.get('gk_away_socks_color', '#ffc107')
        
        team.gk_third_jersey_color = request.POST.get('gk_third_jersey_color', '')
        team.gk_third_shorts_color = request.POST.get('gk_third_shorts_color', '')
        team.gk_third_socks_color = request.POST.get('gk_third_socks_color', '')
        
        # Handle kit image uploads - ADD THIS SECTION
        # Outfield players kits
        if 'home_kit_image' in request.FILES and request.FILES['home_kit_image']:
            team.home_kit_image = request.FILES['home_kit_image']
        
        if 'away_kit_image' in request.FILES and request.FILES['away_kit_image']:
            team.away_kit_image = request.FILES['away_kit_image']
        
        if 'third_kit_image' in request.FILES and request.FILES['third_kit_image']:
            team.third_kit_image = request.FILES['third_kit_image']
        
        # Goalkeeper kits
        if 'gk_home_kit_image' in request.FILES and request.FILES['gk_home_kit_image']:
            team.gk_home_kit_image = request.FILES['gk_home_kit_image']
        
        if 'gk_away_kit_image' in request.FILES and request.FILES['gk_away_kit_image']:
            team.gk_away_kit_image = request.FILES['gk_away_kit_image']
        
        if 'gk_third_kit_image' in request.FILES and request.FILES['gk_third_kit_image']:
            team.gk_third_kit_image = request.FILES['gk_third_kit_image']
        
        # Mark kit colors as set
        team.kit_colors_set = True
        
        try:
            team.save()
            messages.success(request, "✅ Kit colors and images saved successfully!")
            # Redirect to team officials form instead of dashboard
            return redirect('teams:team_officials')
        except Exception as e:
            messages.error(request, f"Error saving kit colors: {str(e)}")
    
    # GET request - show the form with existing images
    return render(request, 'teams/select_kit.html', {
        'team': team
    })

@login_required
def team_manager_dashboard(request):
    """Dashboard for approved team managers"""
    from matches.models import Match
    from referees.models import MatchdaySquad
    from django.utils import timezone
    from datetime import timedelta, datetime
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Get user's approved team
    team = Team.objects.filter(manager=request.user, status='approved').first()
    
    if not team:
        messages.error(request, "You don't have an approved team.")
        return redirect('dashboard')
    
    logger.info(f"Team manager dashboard accessed by: {request.user.username} for team: {team.team_name}")
    
    # Check if kit colors are set
    kit_complete = team.kit_colors_set

    # Show reminder only once for approved teams on first login
    show_kit_prompt = False
    if not kit_complete and not team.kit_setup_prompt_shown:
        show_kit_prompt = True
        team.kit_setup_prompt_shown = True
        team.save(update_fields=['kit_setup_prompt_shown'])
    
    # Get team data
    players = Player.objects.filter(team=team).order_by('jersey_number')
    player_count = players.count()
    captain = players.filter(is_captain=True).first()
    
    # Get league settings for deadlines
    settings = LeagueSettings.get_settings()
    
    # Get upcoming matches for matchday squad management
    today = timezone.now()
    upcoming_matches = Match.objects.filter(
        Q(home_team=team) | Q(away_team=team),
        match_date__gte=today.date(),
        status='scheduled'
    ).order_by('round_number', 'match_date', 'kickoff_time')[:5]
    
    logger.info(f"Found {upcoming_matches.count()} upcoming matches for team: {team.team_name}")
    
    # Find the current active round (most recent match that can be selected)
    current_round = None
    active_match = None
    
    if upcoming_matches.exists():
        # Get the first upcoming match's round
        first_match = upcoming_matches.first()
        current_round = first_match.round_number
        
        # Check if previous round is completed
        if current_round and current_round > 1:
            previous_round_matches = Match.objects.filter(
                Q(home_team=team) | Q(away_team=team),
                round_number=current_round - 1
            )
            
            # If previous round has any unplayed matches, block current round
            if previous_round_matches.filter(status='scheduled').exists():
                current_round = None  # Block squad submission
            else:
                active_match = first_match  # Only the first match in current round
        else:
            # First round or no round number, allow first match
            active_match = first_match
    
    # Prepare matches data with squad info
    matches_data = []
    for match in upcoming_matches:
        squad = MatchdaySquad.objects.filter(match=match, team=team).first()
        
        # Determine if this match can have squad submitted
        can_submit = False
        if active_match and match.id == active_match.id:
            # Check if within submission window (4 hours before kick-off) and not after kick-off
            try:
                if match.kickoff_time:
                    # Handle kickoff_time as string (CharField)
                    kickoff_time = match.kickoff_time
                    if isinstance(kickoff_time, str):
                        try:
                            kickoff_time = datetime.strptime(kickoff_time, '%H:%M:%S').time()
                        except (ValueError, AttributeError):
                            try:
                                kickoff_time = datetime.strptime(kickoff_time, '%H:%M').time()
                            except (ValueError, AttributeError):
                                kickoff_time = datetime.strptime('12:00', '%H:%M').time()  # Default to noon
                    
                    match_datetime = timezone.make_aware(
                        timezone.datetime.combine(match.match_date, kickoff_time)
                    )
                else:
                    # If no kickoff time, assume noon
                    match_datetime = timezone.make_aware(
                        timezone.datetime.combine(match.match_date, datetime.strptime('12:00', '%H:%M').time())
                    )
                time_until_match = match_datetime - today
                # Can submit if match hasn't started yet and within 4 hours window
                can_submit = time_until_match > timedelta(hours=0) and time_until_match <= timedelta(hours=4)
            except (ValueError, TypeError):
                # If date/time parsing fails, allow submission
                can_submit = True
        
        matches_data.append({
            'match': match,
            'squad': squad,
            'can_submit': can_submit,
            'is_active_match': active_match and match.id == active_match.id,
            'squad_status': squad.get_status_display() if squad else 'Not Submitted',
            'can_view_only': squad.can_view_only() if squad else False,
            'can_request_edit': squad.can_request_edit() if squad else False,
        })
    
    logger.info(f"Prepared {len(matches_data)} matches with squad info. Current round: {current_round}")

    # ── Tournament data ─────────────────────────────────────────────────
    from tournaments.models import (
        Tournament, TournamentTeamRegistration, TournamentMatch,
        TournamentMatchdaySquad, ExternalTeam,
    )

    team_tournament_regs = TournamentTeamRegistration.objects.filter(
        team=team,
    ).select_related('tournament')

    external_tournament_regs = TournamentTeamRegistration.objects.none()
    ext_teams = ExternalTeam.objects.filter(manager_user=request.user)
    if ext_teams.exists():
        external_tournament_regs = TournamentTeamRegistration.objects.filter(
            external_team__in=ext_teams,
        ).select_related('tournament', 'external_team')

    open_tournaments = Tournament.objects.filter(
        status='registration',
        registration_deadline__gte=timezone.now(),
    ).exclude(registrations__team=team)

    # Tournament matches for this team
    all_regs = list(
        TournamentTeamRegistration.objects.filter(team=team, status='approved')
    ) + list(
        TournamentTeamRegistration.objects.filter(
            external_team__manager_user=request.user, status='approved'
        )
    )
    tournament_matches_data = []
    for reg in all_regs:
        t_matches = TournamentMatch.objects.filter(
            Q(home_team=reg) | Q(away_team=reg),
            status='scheduled',
        ).select_related('tournament', 'home_team', 'away_team').order_by('match_date')
        for tm in t_matches:
            t_squad = TournamentMatchdaySquad.objects.filter(match=tm, team_registration=reg).first()
            tournament_matches_data.append({
                'match': tm,
                'reg': reg,
                'squad': t_squad,
                'starting_count': t_squad.squad_players.filter(is_starting=True).count() if t_squad else 0,
                'subs_count': t_squad.squad_players.filter(is_starting=False).count() if t_squad else 0,
            })

    context = {
        'team': team,
        'players': players,
        'player_count': player_count,
        'captain_name': captain.full_name if captain else "Not set",
        'kit_complete': kit_complete,
        'show_kit_prompt': show_kit_prompt,
        'recent_players': players.order_by('-registration_date')[:10],
        'league_settings': settings,  # Add this for consistency with home template
        'player_registration_deadline': settings.player_registration_deadline,
        'player_registration_closed_date': settings.player_registration_closed_date,
        'transfer_window_deadline': settings.transfer_window_deadline,
        'transfer_window_closed_date': settings.transfer_window_closed_date,
        'player_registration_open': settings.player_registration_open,
        'transfer_window_open': settings.transfer_window_open,
        'upcoming_matches': matches_data,
        'current_round': current_round,
        # Tournament
        'team_tournament_regs': team_tournament_regs,
        'external_tournament_regs': external_tournament_regs,
        'open_tournaments': open_tournaments,
        'tournament_matches_data': tournament_matches_data,
    }
    return render(request, 'dashboard/team_manager.html', context)

@login_required
def add_player_action(request):
    """Handle ONLY the Add Player button - accessible to team managers and admins"""
    # Check if player registration is open
    settings = LeagueSettings.get_settings()
    is_admin = request.user.is_staff or request.user.is_superuser
    
    if not settings.player_registration_open and not is_admin:
        return render(request, 'teams/registration_closed.html', {
            'title': 'Player Registration Closed',
            'message': 'Player registration is currently closed. Please check back later or contact the league administrator.',
            'back_url': 'teams:team_manager_dashboard',
            'deadline': settings.player_registration_deadline
        })
    
    # Get team - either from query param (admin) or user's team (manager)
    if is_admin and request.GET.get('team_id'):
        team = get_object_or_404(Team, id=request.GET.get('team_id'), status='approved')
    elif is_admin and request.POST.get('team_id'):
        team = get_object_or_404(Team, id=request.POST.get('team_id'), status='approved')
    else:
        # Get user's approved team (for team managers)
        team = Team.objects.filter(manager=request.user, status='approved').first()
        
        if not team:
            messages.error(request, "You don't have an approved team.")
            return redirect('dashboard')
        
        if not team.kit_colors_set:
            messages.error(request, "Please set your team kit colors first!")
            return redirect('teams:select_kit_colors')
    
    if request.method == 'POST':
        # Get form data
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        date_of_birth = request.POST.get('date_of_birth')
        id_number = request.POST.get('id_number', '').strip()
        nationality = request.POST.get('nationality', 'Kenyan')
        position = request.POST.get('position')
        jersey_number = request.POST.get('jersey_number')
        fkf_license_number = request.POST.get('fkf_license_number', '')
        license_expiry_date = request.POST.get('license_expiry_date')
        is_captain = 'is_captain' in request.POST
        
        # Validate required fields
        if not all([first_name, last_name, date_of_birth, id_number, position, jersey_number]):
            messages.error(request, "Please fill all required fields marked with *")
            return redirect('teams:add_players_approved')
        
        try:
            # Check if ID number already exists
            if Player.objects.filter(id_number=id_number).exists():
                messages.error(request, f'ID Number {id_number} is already registered.')
                return redirect('teams:add_players_approved')
            
            # Check jersey number uniqueness for this team
            if Player.objects.filter(team=team, jersey_number=jersey_number).exists():
                messages.error(request, f'Jersey number {jersey_number} is already taken.')
                return redirect('teams:add_players_approved')
            
            # If setting as captain, remove captain status from other players
            if is_captain:
                Player.objects.filter(team=team, is_captain=True).update(is_captain=False)
            
            # Create player
            player = Player.objects.create(
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date_of_birth,
                id_number=id_number,
                nationality=nationality,
                position=position,
                jersey_number=jersey_number,
                team=team,
                fkf_license_number=fkf_license_number,
                license_expiry_date=license_expiry_date if license_expiry_date else None,
                is_captain=is_captain
            )
            
            # Handle photo upload
            if 'photo' in request.FILES and request.FILES['photo']:
                player.photo = request.FILES['photo']
                player.save()
            
            messages.success(request, f'✅ Player {player.full_name} added successfully!')
            
            # Redirect back to add players page (Add & Continue)
            if is_admin:
                return redirect(f"{reverse('teams:add_players_approved')}?team_id={team.id}")
            else:
                return redirect('teams:add_players_approved')
                
        except Exception as e:
            messages.error(request, f'Error saving player: {str(e)}')
            if is_admin and team:
                return redirect(f"{reverse('teams:add_players_approved')}?team_id={team.id}")
            else:
                return redirect('teams:add_players_approved')
    
    # If not POST, redirect to add players page
    if is_admin and request.GET.get('team_id'):
        return redirect(f"{reverse('teams:add_players_approved')}?team_id={request.GET.get('team_id')}")
    return redirect('teams:add_players_approved')

@login_required
def add_players_to_approved_team(request):
    """Show player management form - accessible to team managers and admins"""
    settings = LeagueSettings.get_settings()

    if not settings.player_registration_open:
        # Allow admins to bypass registration closure
        if not (request.user.is_staff or request.user.is_superuser):
            return render(request, 'teams/registration_closed.html', {
                'title': 'Player Registration Closed',
                'message': 'Player registration is currently closed. Please check back later or contact the league admin.',
                'deadline': settings.player_registration_deadline,
                'back_url': request.META.get('HTTP_REFERER', '/'),
            })

    # Check if user is admin/staff or team manager
    is_admin = request.user.is_staff or request.user.is_superuser
    
    if is_admin:
        # Admin can select any team
        team_id = request.GET.get('team_id')
        if team_id:
            team = get_object_or_404(Team, id=team_id, status='approved')
        else:
            # Show team selection page for admins
            teams = Team.objects.filter(status='approved').order_by('team_name')
            return render(request, 'teams/admin_select_team_players.html', {
                'teams': teams
            })
    else:
        # Get user's approved team (for team managers)
        team = Team.objects.filter(manager=request.user, status='approved').first()
        
        if not team:
            messages.error(request, "You don't have an approved team.")
            return redirect('dashboard')
        
        # Check if kit colors are set
        if not team.kit_colors_set:
            messages.error(request, "Please set your team kit colors first!")
            return redirect('teams:select_kit_colors')
    
    # GET request only - show the form
    players = Player.objects.filter(team=team).order_by('jersey_number')
    player_count = players.count()
    
    return render(request, 'teams/add_players_approved.html', {
        'team': team,
        'players': players,
        'player_count': player_count,
        'is_admin': is_admin
    })


# =============================================================================
# TRANSFER SYSTEM VIEWS
# =============================================================================

@login_required
def search_players(request):
    """Select team and player to request transfer using dropdowns"""
    settings = LeagueSettings.get_settings()
    team = Team.objects.filter(manager=request.user, status='approved').first()
    
    if not team:
        messages.error(request, "You don't have an approved team.")
        return redirect('dashboard')

    if not settings.transfer_window_open:
        return render(request, 'teams/registration_closed.html', {
            'title': 'Transfer Window Closed',
            'message': 'Player transfers are currently closed. Please check back once the window reopens.',
            'deadline': settings.transfer_window_deadline,
            'back_url': request.META.get('HTTP_REFERER', '/'),
        })
    
    # Get all other teams (approved teams excluding user's team)
    all_teams = Team.objects.filter(status='approved').exclude(id=team.id).order_by('team_name')
    
    selected_team_id = request.GET.get('team_id', '')
    selected_players = []
    
    if selected_team_id:
        try:
            selected_team = Team.objects.get(id=selected_team_id, status='approved')
            # Get players from selected team (ordered by jersey number)
            selected_players = Player.objects.filter(team=selected_team).order_by('jersey_number')
        except Team.DoesNotExist:
            pass
    
    context = {
        'team': team,
        'all_teams': all_teams,
        'selected_team_id': selected_team_id,
        'selected_players': selected_players,
        'transfer_window_open': settings.transfer_window_open
    }
    return render(request, 'teams/search_players.html', context)


@login_required
def request_transfer(request, player_id):
    """Team manager requests a player transfer"""
    settings = LeagueSettings.get_settings()
    
    if not settings.transfer_window_open:
        return render(request, 'teams/registration_closed.html', {
            'title': 'Transfer Window Closed',
            'message': 'Player transfers are currently closed. Please check back once the window reopens.',
            'deadline': settings.transfer_window_deadline,
            'back_url': request.META.get('HTTP_REFERER', '/'),
        })
    
    # Get requester's team
    to_team = Team.objects.filter(manager=request.user, status='approved').first()
    if not to_team:
        messages.error(request, "You don't have an approved team.")
        return redirect('dashboard')
    
    # Get the player
    player = get_object_or_404(Player, id=player_id)
    from_team = player.team
    
    # Validation
    if from_team == to_team:
        messages.error(request, "This player is already in your team.")
        return redirect('teams:search_players')
    
    # Check for duplicate pending request
    if TransferRequest.objects.filter(
        player=player,
        to_team=to_team,
        status='pending_parent'
    ).exists():
        messages.error(request, f"You already have a pending transfer request for {player.full_name}.")
        return redirect('teams:search_players')
    
    # Create transfer request
    try:
        transfer = TransferRequest.objects.create(
            player=player,
            from_team=from_team,
            to_team=to_team,
            requested_by=request.user
        )
        messages.success(request, 
            f"✅ Transfer Request Successful! "
            f"You have successfully requested {player.full_name} "
            f"(#{player.jersey_number}, {player.get_position_display()}) from {from_team.team_name}. "
            f"The request is now waiting for approval from {from_team.team_name}'s manager. "
            f"You will be notified once they respond to your request."
        )
    except Exception as e:
        messages.error(request, f"❌ Error: Could not create transfer request. {str(e)}")
    
    return redirect('teams:my_transfer_requests')


@login_required
def my_transfer_requests(request):
    """View all transfer requests (incoming and outgoing)"""
    team = Team.objects.filter(manager=request.user, status='approved').first()
    
    if not team:
        messages.error(request, "You don't have an approved team.")
        return redirect('dashboard')
    
    # Outgoing: Players I want to bring in
    outgoing_requests = TransferRequest.objects.filter(
        to_team=team
    ).select_related('player', 'from_team', 'requested_by').order_by('-request_date')
    
    # Incoming: Players others want from my team
    incoming_requests = TransferRequest.objects.filter(
        from_team=team,
        status='pending_parent'
    ).select_related('player', 'to_team', 'requested_by').order_by('-request_date')
    
    context = {
        'team': team,
        'outgoing_requests': outgoing_requests,
        'incoming_requests': incoming_requests,
        'pending_incoming_count': incoming_requests.count()
    }
    return render(request, 'teams/transfer_requests.html', context)


@login_required
def approve_transfer(request, transfer_id):
    """Parent club approves transfer request"""
    transfer = get_object_or_404(TransferRequest, id=transfer_id)
    team = Team.objects.filter(manager=request.user, status='approved').first()
    
    # Validate ownership
    if transfer.from_team != team:
        messages.error(request, "You can only approve transfers for your own team.")
        return redirect('teams:my_transfer_requests')
    
    # Validate status
    if transfer.status != 'pending_parent':
        messages.error(request, "This transfer request has already been processed.")
        return redirect('teams:my_transfer_requests')
    
    # Approve and execute transfer
    transfer.approve_by_parent(user=request.user, execute_transfer=True)
    
    messages.success(request, 
        f"✅ Transfer approved! {transfer.player.full_name} has been transferred to {transfer.to_team.team_name}."
    )
    return redirect('teams:my_transfer_requests')


@login_required
def reject_transfer(request, transfer_id):
    """Parent club rejects transfer request with reason"""
    transfer = get_object_or_404(TransferRequest, id=transfer_id)
    team = Team.objects.filter(manager=request.user, status='approved').first()
    
    # Validate ownership
    if transfer.from_team != team:
        messages.error(request, "You can only reject transfers for your own team.")
        return redirect('teams:my_transfer_requests')
    
    # Validate status
    if transfer.status != 'pending_parent':
        messages.error(request, "This transfer request has already been processed.")
        return redirect('teams:my_transfer_requests')
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(request, "Please provide a reason for rejection.")
            return redirect('teams:my_transfer_requests')
        
        transfer.reject_by_parent(user=request.user, reason=reason)
        
        messages.success(request, 
            f"❌ Transfer rejected. {transfer.to_team.team_name} has been notified."
        )
        return redirect('teams:my_transfer_requests')
    
    # Show rejection form
    return render(request, 'teams/reject_transfer.html', {
        'transfer': transfer,
        'team': team
    })


@login_required
def cancel_transfer(request, transfer_id):
    """Requester cancels their transfer request"""
    transfer = get_object_or_404(TransferRequest, id=transfer_id)
    team = Team.objects.filter(manager=request.user, status='approved').first()
    
    # Validate requester
    if transfer.to_team != team:
        messages.error(request, "You can only cancel your own transfer requests.")
        return redirect('teams:my_transfer_requests')
    
    if transfer.cancel_by_requester():
        messages.success(request, f"Transfer request for {transfer.player.full_name} cancelled.")
    else:
        messages.error(request, "Cannot cancel this transfer request (already processed).")
    
    return redirect('teams:my_transfer_requests')


# =============================================================================
# TEAM OFFICIALS VIEWS
# =============================================================================

@login_required
def team_officials(request):
    """Manage team officials - can be accessed anytime after approval"""
    team = Team.objects.filter(manager=request.user, status='approved').first()
    
    if not team:
        messages.error(request, "You don't have an approved team.")
        return redirect('dashboard')
    
    # Get existing officials
    officials = TeamOfficial.objects.filter(team=team).order_by('position')
    
    # Check which positions are filled
    filled_positions = officials.values_list('position', flat=True)
    required_positions = ['head_coach', 'assistant_coach', 'goalkeeper_coach', 'team_doctor', 'team_patron']
    missing_positions = [pos for pos in required_positions if pos not in filled_positions]
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'add_official':
            form = TeamOfficialForm(request.POST, request.FILES)
            if form.is_valid():
                official = form.save(commit=False)
                official.team = team
                try:
                    official.save()
                    messages.success(request, f"\u2705 {official.get_position_display()} added successfully!")
                    return redirect('teams:team_officials')
                except Exception as e:
                    messages.error(request, f"Error: {str(e)}")
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
        
        elif action == 'continue':
            # Check if all required positions are filled
            if missing_positions:
                messages.warning(request, f"Please add: {', '.join([dict(TeamOfficial.POSITION_CHOICES)[pos] for pos in missing_positions])}")
            else:
                messages.success(request, "\u2705 All team officials registered! You can now add players.")
                return redirect('teams:add_players_approved')
    
    form = TeamOfficialForm()
    
    context = {
        'team': team,
        'officials': officials,
        'form': form,
        'missing_positions': missing_positions,
        'filled_count': officials.count(),
        'total_required': len(required_positions),
    }
    return render(request, 'teams/team_officials.html', context)


@login_required
def delete_official(request, official_id):
    """Delete a team official"""
    official = get_object_or_404(TeamOfficial, id=official_id)
    team = Team.objects.filter(manager=request.user, status='approved').first()
    
    if official.team != team:
        messages.error(request, "You can only delete officials from your own team.")
        return redirect('teams:team_officials')
    
    official_name = official.full_name
    official.delete()
    messages.success(request, f"\u274c {official_name} removed.")
    return redirect('teams:team_officials')


# =============================================================================
# ADMIN PLAYER MANAGEMENT VIEWS
# =============================================================================

@login_required
@user_passes_test(admin_or_league_manager_required)
def admin_manage_players(request):
    """Admin view to manage all players - list, search, filter"""
    search_query = request.GET.get('search', '')
    team_filter = request.GET.get('team', '')
    position_filter = request.GET.get('position', '')
    status_filter = request.GET.get('status', '')
    
    players = Player.objects.select_related('team').all()
    
    # Apply filters
    if search_query:
        players = players.filter(
            models.Q(first_name__icontains=search_query) |
            models.Q(last_name__icontains=search_query) |
            models.Q(id_number__icontains=search_query) |
            models.Q(fkf_license_number__icontains=search_query)
        )
    
    if team_filter:
        players = players.filter(team_id=team_filter)
    
    if position_filter:
        players = players.filter(position=position_filter)
    
    if status_filter == 'suspended':
        players = players.filter(is_suspended=True)
    elif status_filter == 'active':
        players = players.filter(is_suspended=False)
    
    players = players.order_by('team__team_name', 'jersey_number')
    
    # Get teams and stats
    teams = Team.objects.filter(status='approved').order_by('team_name')
    total_players = Player.objects.count()
    suspended_players = Player.objects.filter(is_suspended=True).count()
    
    context = {
        'players': players,
        'teams': teams,
        'search_query': search_query,
        'team_filter': team_filter,
        'position_filter': position_filter,
        'status_filter': status_filter,
        'position_choices': Player.POSITION_CHOICES,
        'total_players': total_players,
        'suspended_players': suspended_players,
    }
    
    return render(request, 'teams/admin_manage_players.html', context)


@login_required
@user_passes_test(admin_or_league_manager_required)
def admin_delete_player(request, player_id):
    """Admin delete a player with confirmation"""
    player = get_object_or_404(Player, id=player_id)
    
    if request.method == 'POST':
        team = player.team
        player_name = player.full_name
        player.delete()
        messages.success(request, f'✅ Player {player_name} deleted successfully from {team.team_name}')
        return redirect('teams:admin_manage_players')
    
    context = {'player': player}
    return render(request, 'teams/admin_delete_player.html', context)


@login_required
@user_passes_test(admin_or_league_manager_required)
def admin_suspend_player(request, player_id):
    """Admin suspend a player with reason and duration"""
    player = get_object_or_404(Player, id=player_id)
    
    if request.method == 'POST':
        suspension_matches = request.POST.get('suspension_matches')
        suspension_reason = request.POST.get('suspension_reason')
        
        if not suspension_matches or not suspension_reason:
            messages.error(request, '❌ Both suspension matches and reason are required')
            return redirect('teams:admin_suspend_player', player_id=player_id)
        
        try:
            matches = int(suspension_matches)
            if matches < 1:
                raise ValueError("Matches must be positive")
            
            player.is_suspended = True
            player.suspension_reason = suspension_reason
            # Store suspension matches count in suspension_end field temporarily
            # You may want to add a separate field for this
            player.suspension_matches = matches
            player.save()
            
            messages.success(request, f'✅ {player.full_name} suspended for {matches} match(es): {suspension_reason}')
            return redirect('teams:admin_manage_players')
            
        except ValueError:
            messages.error(request, '❌ Invalid number of matches')
            return redirect('teams:admin_suspend_player', player_id=player_id)
    
    context = {'player': player}
    return render(request, 'teams/admin_suspend_player.html', context)


@login_required
@user_passes_test(admin_or_league_manager_required)
def admin_unsuspend_player(request, player_id):
    """Admin unsuspend a player"""
    player = get_object_or_404(Player, id=player_id)
    
    if request.method == 'POST':
        player.is_suspended = False
        player.suspension_reason = ''
        player.suspension_end = None
        if hasattr(player, 'suspension_matches'):
            player.suspension_matches = 0
        player.save()
        
        messages.success(request, f'✅ {player.full_name} unsuspended successfully')
        return redirect('teams:admin_manage_players')
    
    context = {'player': player}
    return render(request, 'teams/admin_unsuspend_player.html', context)


@login_required
@user_passes_test(admin_or_league_manager_required)
def admin_edit_player(request, player_id):
    """Admin edit player information"""
    player = get_object_or_404(Player, id=player_id)
    
    if request.method == 'POST':
        # Update personal information
        player.first_name = request.POST.get('first_name', player.first_name)
        player.last_name = request.POST.get('last_name', player.last_name)
        player.date_of_birth = request.POST.get('date_of_birth', player.date_of_birth)
        player.nationality = request.POST.get('nationality', player.nationality)
        player.id_number = request.POST.get('id_number', player.id_number)
        
        # Update FKF license information
        player.fkf_license_number = request.POST.get('fkf_license_number', player.fkf_license_number)
        license_expiry = request.POST.get('license_expiry_date')
        if license_expiry:
            player.license_expiry_date = license_expiry
        
        # Update team information
        team_id = request.POST.get('team')
        if team_id:
            try:
                team = Team.objects.get(id=team_id, status='approved')
                player.team = team
            except Team.DoesNotExist:
                messages.error(request, '❌ Invalid team selected')
                return redirect('teams:admin_edit_player', player_id=player_id)
        
        player.position = request.POST.get('position', player.position)
        player.jersey_number = request.POST.get('jersey_number', player.jersey_number)
        player.is_captain = request.POST.get('is_captain') == 'on'
        
        # Update statistics (admin can manually adjust)
        try:
            player.goals_scored = int(request.POST.get('goals_scored', player.goals_scored))
            player.yellow_cards = int(request.POST.get('yellow_cards', player.yellow_cards))
            player.red_cards = int(request.POST.get('red_cards', player.red_cards))
            player.matches_played = int(request.POST.get('matches_played', player.matches_played))
        except ValueError:
            messages.error(request, '❌ Invalid number in statistics')
            return redirect('teams:admin_edit_player', player_id=player_id)
        
        # Handle photo upload
        if 'photo' in request.FILES:
            player.photo = request.FILES['photo']
        
        try:
            player.save()
            messages.success(request, f'✅ Player {player.full_name} updated successfully')
            return redirect('teams:admin_manage_players')
        except Exception as e:
            messages.error(request, f'❌ Error updating player: {str(e)}')
            return redirect('teams:admin_edit_player', player_id=player_id)
    
    # GET request - show form
    teams = Team.objects.filter(status='approved').order_by('team_name')
    
    context = {
        'player': player,
        'teams': teams,
        'position_choices': Player.POSITION_CHOICES,
    }
    return render(request, 'teams/admin_edit_player.html', context)


@login_required
@user_passes_test(admin_or_league_manager_required)
def admin_add_team_official(request):
    """Admin add team official with team selection"""
    if request.method == 'POST':
        team_id = request.POST.get('team_id')
        full_name = request.POST.get('full_name')
        position = request.POST.get('position')
        phone_number = request.POST.get('phone_number', '').strip()
        email = request.POST.get('email', '')
        
        # Validate phone format: +254 followed by 9 digits
        import re
        if not re.match(r'^\+254\d{9}$', phone_number):
            messages.error(request, '❌ Phone number must be in the format +254XXXXXXXXX (country code + 9 digits)')
            teams = Team.objects.filter(status='approved').order_by('team_name')
            positions = TeamOfficial.POSITION_CHOICES
            return render(request, 'teams/admin_add_official.html', {'teams': teams, 'positions': positions})
        
        try:
            team = Team.objects.get(id=team_id, status='approved')
            
            official = TeamOfficial.objects.create(
                team=team,
                full_name=full_name,
                position=position,
                phone_number=phone_number,
                email=email
            )
            
            messages.success(request, f'✅ Official {full_name} added to {team.team_name}')
            return redirect('teams:admin_manage_officials')
            
        except Team.DoesNotExist:
            messages.error(request, '❌ Invalid team selected')
        except Exception as e:
            messages.error(request, f'❌ Error adding official: {str(e)}')
    
    teams = Team.objects.filter(status='approved').order_by('team_name')
    positions = TeamOfficial.POSITION_CHOICES
    
    context = {
        'teams': teams,
        'positions': positions
    }
    
    return render(request, 'teams/admin_add_official.html', context)


@login_required
@user_passes_test(admin_or_league_manager_required)
def admin_manage_officials(request):
    """Admin view to manage all team officials"""
    search_query = request.GET.get('search', '')
    team_filter = request.GET.get('team', '')
    position_filter = request.GET.get('position', '')
    status_filter = request.GET.get('status', '')
    
    officials = TeamOfficial.objects.select_related('team').all()
    
    # Apply filters
    if search_query:
        officials = officials.filter(
            models.Q(full_name__icontains=search_query) |
            models.Q(phone_number__icontains=search_query) |
            models.Q(email__icontains=search_query)
        )
    
    if team_filter:
        officials = officials.filter(team_id=team_filter)
    
    if position_filter:
        officials = officials.filter(position=position_filter)
    
    if status_filter:
        if status_filter == 'suspended':
            officials = officials.filter(is_suspended=True)
        elif status_filter == 'active':
            officials = officials.filter(is_suspended=False)
    
    officials = officials.order_by('team__team_name', 'position')
    
    # Get teams for filter
    teams = Team.objects.filter(status='approved').order_by('team_name')
    
    # Stats
    total_officials = TeamOfficial.objects.count()
    suspended_officials = TeamOfficial.objects.filter(is_suspended=True).count()
    active_officials = total_officials - suspended_officials
    
    context = {
        'officials': officials,
        'teams': teams,
        'search_query': search_query,
        'team_filter': team_filter,
        'position_filter': position_filter,
        'status_filter': status_filter,
        'position_choices': TeamOfficial.POSITION_CHOICES,
        'total_officials': total_officials,
        'suspended_officials': suspended_officials,
        'active_officials': active_officials,
    }
    
    return render(request, 'teams/admin_manage_officials.html', context)


@login_required
@user_passes_test(admin_or_league_manager_required)
def admin_suspend_official(request, official_id):
    """Admin suspend a team official"""
    official = get_object_or_404(TeamOfficial, id=official_id)
    
    if request.method == 'POST':
        suspension_matches = request.POST.get('suspension_matches', 0)
        suspension_reason = request.POST.get('suspension_reason', '')
        
        try:
            official.is_suspended = True
            official.suspension_matches = int(suspension_matches)
            official.suspension_reason = suspension_reason
            official.save()
            
            messages.success(request, f'✅ Official {official.full_name} suspended for {suspension_matches} matches')
            return redirect('teams:admin_manage_officials')
        except Exception as e:
            messages.error(request, f'❌ Error suspending official: {str(e)}')
    
    context = {
        'official': official,
    }
    return render(request, 'teams/admin_suspend_official.html', context)


@login_required
@user_passes_test(admin_or_league_manager_required)
def admin_unsuspend_official(request, official_id):
    """Admin unsuspend a team official"""
    official = get_object_or_404(TeamOfficial, id=official_id)
    
    if request.method == 'POST':
        official.is_suspended = False
        official.suspension_matches = 0
        official.suspension_reason = ''
        official.suspension_end = None
        official.save()
        
        messages.success(request, f'✅ Official {official.full_name} suspension lifted')
        return redirect('teams:admin_manage_officials')
    
    context = {
        'official': official,
    }
    return render(request, 'teams/admin_unsuspend_official.html', context)


@login_required
def view_approved_squad(request, match_id):
    """Team manager view of their approved matchday squad (read-only)"""
    from matches.models import Match
    from referees.models import MatchdaySquad, SquadPlayer
    from django.utils import timezone
    
    # Get the match
    match = get_object_or_404(Match, id=match_id)
    
    # Get user's approved team
    team = Team.objects.filter(manager=request.user, status='approved').first()
    
    if not team:
        messages.error(request, "You don't have an approved team.")
        return redirect('teams:team_manager_dashboard')
    
    # Check if team is playing in this match
    if team not in [match.home_team, match.away_team]:
        messages.error(request, "Your team is not playing in this match.")
        return redirect('teams:team_manager_dashboard')
    
    # Get the approved squad
    squad = MatchdaySquad.objects.filter(
        match=match, 
        team=team, 
        status='approved'
    ).first()
    
    if not squad:
        messages.error(request, "No approved squad found for this match.")
        return redirect('teams:team_manager_dashboard')
    
    # Check if match has kicked off (only show after kickoff)
    if match.match_date and match.kickoff_time:
        kickoff_time = match.kickoff_time
        if isinstance(kickoff_time, str):
            try:
                from datetime import datetime
                kickoff_time = datetime.strptime(kickoff_time, '%H:%M:%S').time()
            except (ValueError, AttributeError):
                try:
                    kickoff_time = datetime.strptime(kickoff_time, '%H:%M').time()
                except (ValueError, AttributeError):
                    messages.error(request, "Invalid kickoff time format.")
                    return redirect('teams:team_manager_dashboard')
        
        match_datetime = timezone.make_aware(
            timezone.datetime.combine(match.match_date, kickoff_time)
        )
        
        if timezone.now() < match_datetime:
            messages.warning(request, "Squad details will be available after match kickoff.")
            return redirect('teams:team_manager_dashboard')
    else:
        messages.error(request, "Match timing not set.")
        return redirect('teams:team_manager_dashboard')
    
    # Get squad players
    starting_players = squad.squad_players.filter(is_starting=True).select_related('player').order_by('position_order')
    substitute_players = squad.squad_players.filter(is_starting=False).select_related('player').order_by('jersey_number')
    
    # Get completed substitutions for this match
    completed_subs = []
    if hasattr(match, 'substitutions'):
        completed_subs = match.substitutions.filter(team=team).order_by('minute')
    
    context = {
        'match': match,
        'team': team,
        'squad': squad,
        'starting_players': starting_players,
        'substitute_players': substitute_players,
        'completed_subs': completed_subs,
        'title': f'Approved Squad - {match.home_team} vs {match.away_team}',
    }
    
    return render(request, 'teams/view_approved_squad.html', context)


@login_required
@user_passes_test(admin_or_league_manager_required)
def admin_manage_officials(request):
    """Admin view to manage team officials"""
    officials = TeamOfficial.objects.select_related('team').order_by('team__team_name', 'full_name')
    
    context = {
        'officials': officials,
        'title': 'Manage Team Officials',
    }
    return render(request, 'teams/admin_manage_officials.html', context)


@login_required
@user_passes_test(admin_or_league_manager_required)
def admin_add_team_official(request):
    """Admin add a team official"""
    if request.method == 'POST':
        team_id = request.POST.get('team_id')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        position = request.POST.get('position')
        mobile = request.POST.get('mobile', '').strip()
        
        if not all([team_id, first_name, last_name, position]):
            messages.error(request, "All fields are required.")
            return redirect('teams:admin_manage_officials')
        
        # Validate phone format: +254 followed by 9 digits
        import re
        if not re.match(r'^\+254\d{9}$', mobile):
            messages.error(request, "Phone number must be in the format +254XXXXXXXXX (country code + 9 digits)")
            return redirect('teams:admin_manage_officials')
        
        try:
            team = Team.objects.get(id=team_id)
            TeamOfficial.objects.create(
                team=team,
                first_name=first_name,
                last_name=last_name,
                position=position,
                mobile=mobile
            )
            messages.success(request, f"Official {first_name} {last_name} added to {team.team_name}")
        except Exception as e:
            messages.error(request, f"Error adding official: {str(e)}")
        
        return redirect('teams:admin_manage_officials')
    
    teams = Team.objects.filter(status='approved').order_by('team_name')
    context = {
        'teams': teams,
        'title': 'Add Team Official',
    }
    return render(request, 'teams/admin_add_official.html', context)


@login_required
@user_passes_test(admin_or_league_manager_required)
def admin_suspend_official(request, official_id):
    """Admin suspend a team official"""
    official = get_object_or_404(TeamOfficial, id=official_id)
    
    if request.method == 'POST':
        matches = request.POST.get('matches', 0)
        reason = request.POST.get('reason', '').strip()
        
        official.is_suspended = True
        official.suspension_matches = int(matches) if matches else 0
        official.suspension_reason = reason
        official.suspension_end = None
        official.save()
        
        messages.success(request, f'Official {official.full_name} suspended')
        return redirect('teams:admin_manage_officials')
    
    context = {
        'official': official,
        'title': 'Suspend Team Official',
    }
    return render(request, 'teams/admin_suspend_official.html', context)


@login_required
@user_passes_test(admin_or_league_manager_required)
def admin_unsuspend_official(request, official_id):
    """Admin unsuspend a team official"""
    official = get_object_or_404(TeamOfficial, id=official_id)
    
    if request.method == 'POST':
        official.is_suspended = False
        official.suspension_matches = 0
        official.suspension_reason = ''
        official.suspension_end = None
        official.save()
        
        messages.success(request, f'Official {official.full_name} suspension lifted')
        return redirect('teams:admin_manage_officials')
    
    context = {
        'official': official,
        'title': 'Unsuspend Team Official',
    }
    return render(request, 'teams/admin_unsuspend_official.html', context)


@login_required
@user_passes_test(admin_or_league_manager_required)
def admin_delete_official(request, official_id):
    """Admin delete a team official"""
    official = get_object_or_404(TeamOfficial, id=official_id)
    
    if request.method == 'POST':
        team = official.team
        official_name = official.full_name
        official.delete()
        messages.success(request, f'Official {official_name} removed from {team.team_name}')
        return redirect('teams:admin_manage_officials')
    
    context = {
        'official': official,
        'title': 'Delete Team Official',
    }
    return render(request, 'teams/admin_delete_official.html', context)