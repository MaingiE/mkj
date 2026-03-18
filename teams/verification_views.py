"""
MKJ SUPA CUP — Player Clearance & Verification Views
===============================================
Step-by-step verification workflow:
  Step 1: Document Verification (existing — admin reviews ID, birth cert, photo)
  Step 2: Huduma Kenya Age Verification (IPRS check)
  Step 3: FIFA Connect Higher-League Check (flag off ineligible players)
  Step 4: Final Clearance (only if Steps 1-3 pass)

Accessible by: Admin, Competition Manager, Secretary General (admin role)
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q, Count, Case, When, CharField, Value
from functools import wraps

from accounts.models import UserRole
from teams.models import (
    Player, PlayerVerificationLog, VerificationStep,
    VerificationStatus, HudumaVerificationStatus, FIFAConnectStatus,
    PlayerStatus, RejectionReason,
)
from teams.fifa_connect_service import FIFAConnectService
from teams.huduma_service import HudumaKenyaService
from teams.utils import save_base64_photo


# ── Role decorator ────────────────────────────────────────────────────────────
def clearance_role_required(view):
    """Only Admin, Competition Manager, Verification Officer can access clearance views."""
    @wraps(view)
    @login_required(login_url='web_login')
    def wrapper(request, *args, **kwargs):
        allowed_roles = ('admin', 'competition_manager', 'verification_officer')
        if request.user.role not in allowed_roles and not request.user.is_superuser:
            messages.error(request, 'You do not have permission to access player clearance.')
            return redirect('dashboard')
        return view(request, *args, **kwargs)
    return wrapper


# ══════════════════════════════════════════════════════════════════════════════
#   CLEARANCE DASHBOARD — Overview of all verification steps
# ══════════════════════════════════════════════════════════════════════════════

@clearance_role_required
def player_clearance_dashboard(request):
    """
    Main dashboard showing overall clearance status for all players.
    Shows stats per verification step and allows filtering.
    """
    # Get filter params
    status_filter = request.GET.get('status', 'all')
    team_filter = request.GET.get('team', '')
    search = request.GET.get('q', '')

    players = Player.objects.select_related('team', 'team__county').all()

    if search:
        players = players.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(national_id_number__icontains=search) |
            Q(fifa_connect_id__icontains=search)
        )

    if team_filter:
        players = players.filter(team_id=team_filter)

    if status_filter == 'cleared':
        players = players.filter(
            verification_status=VerificationStatus.VERIFIED,
            huduma_status=HudumaVerificationStatus.VERIFIED,
            fifa_connect_status=FIFAConnectStatus.CLEAR,
        )
    elif status_filter == 'pending':
        players = players.filter(
            Q(huduma_status=HudumaVerificationStatus.NOT_CHECKED) |
            Q(fifa_connect_status=FIFAConnectStatus.NOT_CHECKED) |
            Q(verification_status=VerificationStatus.PENDING)
        )
    elif status_filter == 'flagged':
        players = players.filter(
            Q(fifa_connect_status=FIFAConnectStatus.FLAGGED) |
            Q(huduma_status=HudumaVerificationStatus.FAILED) |
            Q(verification_status=VerificationStatus.REJECTED)
        )

    players = players.order_by('team__name', 'shirt_number')

    # Calculate stats
    all_players = Player.objects.all()
    stats = {
        'total': all_players.count(),
        'fully_cleared': all_players.filter(
            verification_status=VerificationStatus.VERIFIED,
            huduma_status=HudumaVerificationStatus.VERIFIED,
            fifa_connect_status=FIFAConnectStatus.CLEAR,
        ).count(),
        'docs_pending': all_players.filter(verification_status=VerificationStatus.PENDING).count(),
        'docs_verified': all_players.filter(verification_status=VerificationStatus.VERIFIED).count(),
        'huduma_not_checked': all_players.filter(huduma_status=HudumaVerificationStatus.NOT_CHECKED).count(),
        'huduma_verified': all_players.filter(huduma_status=HudumaVerificationStatus.VERIFIED).count(),
        'huduma_failed': all_players.filter(huduma_status=HudumaVerificationStatus.FAILED).count(),
        'fifa_not_checked': all_players.filter(fifa_connect_status=FIFAConnectStatus.NOT_CHECKED).count(),
        'fifa_clear': all_players.filter(fifa_connect_status=FIFAConnectStatus.CLEAR).count(),
        'fifa_flagged': all_players.filter(fifa_connect_status=FIFAConnectStatus.FLAGGED).count(),
    }

    from teams.models import Team
    teams = Team.objects.filter(status='registered').order_by('name')

    return render(request, 'portal/player_clearance_dashboard.html', {
        'players': players,
        'stats': stats,
        'teams': teams,
        'status_filter': status_filter,
        'team_filter': team_filter,
        'search': search,
    })


# ══════════════════════════════════════════════════════════════════════════════
#   PLAYER CLEARANCE DETAIL — Step-by-step for a single player
# ══════════════════════════════════════════════════════════════════════════════

@clearance_role_required
def player_clearance_detail(request, player_pk):
    """
    Detailed clearance view for a single player.
    Shows all 3 verification steps with status and actions.
    """
    player = get_object_or_404(
        Player.objects.select_related('team', 'team__county',
                                       'verified_by', 'huduma_verified_by',
                                       'fifa_connect_checked_by'),
        pk=player_pk
    )
    logs = PlayerVerificationLog.objects.filter(player=player).select_related('performed_by')[:20]

    return render(request, 'portal/player_clearance_detail.html', {
        'player': player,
        'clearance': player.clearance_summary,
        'logs': logs,
    })


# ══════════════════════════════════════════════════════════════════════════════
#   STEP 2: HUDUMA KENYA AGE VERIFICATION
# ══════════════════════════════════════════════════════════════════════════════

@clearance_role_required
def huduma_verify_player(request, player_pk):
    """
    Initiate or manually confirm Huduma Kenya age verification.
    Calls the Huduma Kenya API and records the result.
    """
    player = get_object_or_404(Player, pk=player_pk)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'auto_check':
            # Call the Huduma Kenya API
            svc = HudumaKenyaService()
            result = svc.verify_player_age(player)

            if result.is_verified:
                player.huduma_status = HudumaVerificationStatus.VERIFIED
                player.huduma_reference = result.reference_number
                player.huduma_notes = f"Auto-verified. Name: {result.verified_name}"
                if result.verified_dob:
                    player.huduma_notes += f", DOB: {result.verified_dob}"
                # Save IPRS passport photo if returned
                if result.photo:
                    save_base64_photo(player, result.photo)
                messages.success(request, f'✅ Huduma Kenya verification passed for {player.get_full_name()}.')
            elif result.success and not result.person_found:
                player.huduma_status = HudumaVerificationStatus.FAILED
                player.huduma_notes = "Person not found in IPRS records."
                messages.warning(request, f'❌ {player.get_full_name()} not found in Huduma Kenya IPRS.')
            elif result.success and not result.age_matches:
                player.huduma_status = HudumaVerificationStatus.FAILED
                player.huduma_notes = (
                    f"DOB mismatch. Claimed: {player.date_of_birth}, "
                    f"IPRS: {result.verified_dob}"
                )
                messages.warning(request, f'❌ Age mismatch for {player.get_full_name()} — DOB does not match IPRS records.')
            else:
                player.huduma_status = HudumaVerificationStatus.PENDING
                player.huduma_notes = f"API error: {result.error_message}"
                messages.error(request, f'⚠️ Huduma Kenya API error: {result.error_message}')

            player.huduma_verified_at = timezone.now()
            player.huduma_verified_by = request.user
            player.save()

            # Log the action
            PlayerVerificationLog.objects.create(
                player=player,
                step=VerificationStep.HUDUMA,
                action='auto_check',
                result=player.huduma_status,
                details={
                    'reference': result.reference_number,
                    'person_found': result.person_found,
                    'age_matches': result.age_matches,
                    'verified_name': result.verified_name,
                    'simulation': result.raw_response.get('_simulation', False),
                },
                notes=player.huduma_notes,
                performed_by=request.user,
            )

        elif action == 'manual_verify':
            # Admin manually confirms age verification (e.g. physical visit to Huduma)
            ref = request.POST.get('reference', '')
            notes = request.POST.get('notes', '')
            player.huduma_status = HudumaVerificationStatus.VERIFIED
            player.huduma_reference = ref
            player.huduma_notes = f"Manually verified by {request.user.get_full_name()}. {notes}"
            player.huduma_verified_at = timezone.now()
            player.huduma_verified_by = request.user
            player.save()

            PlayerVerificationLog.objects.create(
                player=player,
                step=VerificationStep.HUDUMA,
                action='manual_verify',
                result='verified',
                details={'reference': ref},
                notes=notes,
                performed_by=request.user,
            )
            messages.success(request, f'✅ Huduma Kenya verification manually confirmed for {player.get_full_name()}.')

        elif action == 'manual_fail':
            notes = request.POST.get('notes', '')
            player.huduma_status = HudumaVerificationStatus.FAILED
            player.huduma_notes = f"Manually failed by {request.user.get_full_name()}. {notes}"
            player.huduma_verified_at = timezone.now()
            player.huduma_verified_by = request.user
            player.status = PlayerStatus.INELIGIBLE
            player.save()

            PlayerVerificationLog.objects.create(
                player=player,
                step=VerificationStep.HUDUMA,
                action='manual_fail',
                result='failed',
                notes=notes,
                performed_by=request.user,
            )
            messages.warning(request, f'❌ Huduma Kenya verification failed for {player.get_full_name()}.')

        elif action == 'reset':
            player.huduma_status = HudumaVerificationStatus.NOT_CHECKED
            player.huduma_reference = ''
            player.huduma_notes = ''
            player.huduma_verified_at = None
            player.huduma_verified_by = None
            player.save()

            PlayerVerificationLog.objects.create(
                player=player,
                step=VerificationStep.HUDUMA,
                action='reset',
                result='not_checked',
                notes='Reset by admin',
                performed_by=request.user,
            )
            messages.info(request, f'🔄 Huduma Kenya verification reset for {player.get_full_name()}.')

        return redirect('player_clearance_detail', player_pk=player.pk)

    return redirect('player_clearance_detail', player_pk=player.pk)


# ══════════════════════════════════════════════════════════════════════════════
#   STEP 3: FIFA CONNECT HIGHER-LEAGUE CHECK
# ══════════════════════════════════════════════════════════════════════════════

@clearance_role_required
def fifa_connect_check_player(request, player_pk):
    """
    Check a player against FIFA Connect for higher-league registrations.
    Flags players found in Regional League, Division 2, Division 1,
    National Super League, or Kenya FKF Premier League.
    """
    player = get_object_or_404(Player, pk=player_pk)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'auto_check':
            # Optionally update FIFA Connect ID from form
            fifa_id = request.POST.get('fifa_connect_id', '').strip()
            if fifa_id:
                player.fifa_connect_id = fifa_id

            # Call the FIFA Connect API
            svc = FIFAConnectService()
            result = svc.check_player(player)

            if result.is_clear:
                player.fifa_connect_status = FIFAConnectStatus.CLEAR
                player.fifa_connect_leagues = []
                player.fifa_connect_notes = "Clear — no higher-league registrations found."
                if result.fifa_connect_id and not player.fifa_connect_id:
                    player.fifa_connect_id = result.fifa_connect_id
                messages.success(request, f'✅ FIFA Connect check CLEAR for {player.get_full_name()}. No higher-league registrations.')

            elif result.is_flagged:
                player.fifa_connect_status = FIFAConnectStatus.FLAGGED
                player.fifa_connect_leagues = result.leagues_found
                player.fifa_connect_notes = result.flag_reason
                if result.fifa_connect_id and not player.fifa_connect_id:
                    player.fifa_connect_id = result.fifa_connect_id
                player.status = PlayerStatus.INELIGIBLE
                player.rejection_reason = RejectionReason.FIFA_CONNECT_FLAGGED
                player.rejection_notes = result.flag_reason
                messages.warning(request, f'🚩 {player.get_full_name()} FLAGGED — registered in higher-level league(s)!')

            elif result.success and not result.player_found:
                player.fifa_connect_status = FIFAConnectStatus.CLEAR
                player.fifa_connect_leagues = []
                player.fifa_connect_notes = "Player not found in FIFA Connect — no higher league record."
                messages.info(request, f'ℹ️ {player.get_full_name()} not found in FIFA Connect. Treated as clear.')

            else:
                player.fifa_connect_status = FIFAConnectStatus.ERROR
                player.fifa_connect_notes = f"API error: {result.error_message}"
                messages.error(request, f'⚠️ FIFA Connect API error: {result.error_message}')

            player.fifa_connect_checked_at = timezone.now()
            player.fifa_connect_checked_by = request.user
            player.save()

            PlayerVerificationLog.objects.create(
                player=player,
                step=VerificationStep.FIFA_CONNECT,
                action='auto_check',
                result=player.fifa_connect_status,
                details={
                    'fifa_connect_id': result.fifa_connect_id,
                    'player_found': result.player_found,
                    'is_flagged': result.is_flagged,
                    'leagues_found': result.leagues_found,
                    'simulation': result.raw_response.get('_simulation', False),
                },
                notes=player.fifa_connect_notes,
                performed_by=request.user,
            )

        elif action == 'manual_clear':
            notes = request.POST.get('notes', '')
            fifa_id = request.POST.get('fifa_connect_id', '').strip()
            if fifa_id:
                player.fifa_connect_id = fifa_id
            player.fifa_connect_status = FIFAConnectStatus.CLEAR
            player.fifa_connect_leagues = []
            player.fifa_connect_notes = f"Manually cleared by {request.user.get_full_name()}. {notes}"
            player.fifa_connect_checked_at = timezone.now()
            player.fifa_connect_checked_by = request.user
            player.save()

            PlayerVerificationLog.objects.create(
                player=player,
                step=VerificationStep.FIFA_CONNECT,
                action='manual_clear',
                result='clear',
                details={'fifa_connect_id': player.fifa_connect_id},
                notes=notes,
                performed_by=request.user,
            )
            messages.success(request, f'✅ FIFA Connect manually cleared for {player.get_full_name()}.')

        elif action == 'manual_flag':
            notes = request.POST.get('notes', '')
            leagues = request.POST.getlist('flagged_leagues')
            player.fifa_connect_status = FIFAConnectStatus.FLAGGED
            player.fifa_connect_leagues = [{"league": l, "status": "manual_flag"} for l in leagues]
            player.fifa_connect_notes = f"Manually flagged by {request.user.get_full_name()}. {notes}"
            player.fifa_connect_checked_at = timezone.now()
            player.fifa_connect_checked_by = request.user
            player.status = PlayerStatus.INELIGIBLE
            player.rejection_reason = RejectionReason.FIFA_CONNECT_FLAGGED
            player.save()

            PlayerVerificationLog.objects.create(
                player=player,
                step=VerificationStep.FIFA_CONNECT,
                action='manual_flag',
                result='flagged',
                details={'leagues': leagues},
                notes=notes,
                performed_by=request.user,
            )
            messages.warning(request, f'🚩 {player.get_full_name()} manually flagged for higher-league registration.')

        elif action == 'reset':
            player.fifa_connect_status = FIFAConnectStatus.NOT_CHECKED
            player.fifa_connect_leagues = []
            player.fifa_connect_notes = ''
            player.fifa_connect_checked_at = None
            player.fifa_connect_checked_by = None
            player.save()

            PlayerVerificationLog.objects.create(
                player=player,
                step=VerificationStep.FIFA_CONNECT,
                action='reset',
                result='not_checked',
                notes='Reset by admin',
                performed_by=request.user,
            )
            messages.info(request, f'🔄 FIFA Connect check reset for {player.get_full_name()}.')

        return redirect('player_clearance_detail', player_pk=player.pk)

    return redirect('player_clearance_detail', player_pk=player.pk)


# ══════════════════════════════════════════════════════════════════════════════
#   STEP 4: FINAL CLEARANCE
# ══════════════════════════════════════════════════════════════════════════════

@clearance_role_required
def player_final_clearance(request, player_pk):
    """
    Grant or revoke final clearance. Only possible when all 3 steps pass.
    """
    player = get_object_or_404(Player, pk=player_pk)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'grant_clearance':
            if not player.is_fully_cleared:
                messages.error(request, 'Cannot grant clearance — not all verification steps have passed.')
                return redirect('player_clearance_detail', player_pk=player.pk)

            player.status = PlayerStatus.ELIGIBLE
            player.save()

            PlayerVerificationLog.objects.create(
                player=player,
                step=VerificationStep.CLEARANCE,
                action='granted',
                result='eligible',
                notes=f"Final clearance granted by {request.user.get_full_name()}",
                performed_by=request.user,
            )
            messages.success(request, f'🎉 Final clearance GRANTED for {player.get_full_name()}. Player is eligible to participate.')

        elif action == 'revoke_clearance':
            notes = request.POST.get('notes', '')
            player.status = PlayerStatus.INELIGIBLE
            player.save()

            PlayerVerificationLog.objects.create(
                player=player,
                step=VerificationStep.CLEARANCE,
                action='revoked',
                result='ineligible',
                notes=f"Clearance revoked by {request.user.get_full_name()}. {notes}",
                performed_by=request.user,
            )
            messages.warning(request, f'⛔ Clearance REVOKED for {player.get_full_name()}.')

        return redirect('player_clearance_detail', player_pk=player.pk)

    return redirect('player_clearance_detail', player_pk=player.pk)


# ══════════════════════════════════════════════════════════════════════════════
#   BULK OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════

@clearance_role_required
def bulk_fifa_connect_check(request):
    """
    Bulk-check multiple players against FIFA Connect.
    Processes all unchecked players for a selected team.
    """
    if request.method == 'POST':
        team_id = request.POST.get('team_id')
        if not team_id:
            messages.error(request, 'Please select a team.')
            return redirect('player_clearance_dashboard')

        players = Player.objects.filter(
            team_id=team_id,
            fifa_connect_status=FIFAConnectStatus.NOT_CHECKED,
        )

        if not players.exists():
            messages.info(request, 'No unchecked players for this team.')
            return redirect('player_clearance_dashboard')

        svc = FIFAConnectService()
        cleared = 0
        flagged = 0
        errors = 0

        for player in players:
            result = svc.check_player(player)

            if result.is_clear:
                player.fifa_connect_status = FIFAConnectStatus.CLEAR
                player.fifa_connect_leagues = []
                player.fifa_connect_notes = "Clear — bulk check."
                if result.fifa_connect_id:
                    player.fifa_connect_id = result.fifa_connect_id
                cleared += 1
            elif result.is_flagged:
                player.fifa_connect_status = FIFAConnectStatus.FLAGGED
                player.fifa_connect_leagues = result.leagues_found
                player.fifa_connect_notes = result.flag_reason
                player.status = PlayerStatus.INELIGIBLE
                player.rejection_reason = RejectionReason.FIFA_CONNECT_FLAGGED
                flagged += 1
            else:
                player.fifa_connect_status = FIFAConnectStatus.ERROR
                player.fifa_connect_notes = result.error_message
                errors += 1

            player.fifa_connect_checked_at = timezone.now()
            player.fifa_connect_checked_by = request.user
            player.save()

            PlayerVerificationLog.objects.create(
                player=player,
                step=VerificationStep.FIFA_CONNECT,
                action='bulk_check',
                result=player.fifa_connect_status,
                details={
                    'is_flagged': result.is_flagged,
                    'leagues_found': result.leagues_found,
                },
                performed_by=request.user,
            )

        messages.success(
            request,
            f'FIFA Connect bulk check complete: {cleared} cleared, '
            f'{flagged} flagged, {errors} errors.'
        )
        return redirect('player_clearance_dashboard')

    return redirect('player_clearance_dashboard')


@clearance_role_required
def bulk_huduma_check(request):
    """
    Bulk Huduma Kenya check for all unchecked players on a team.
    """
    if request.method == 'POST':
        team_id = request.POST.get('team_id')
        if not team_id:
            messages.error(request, 'Please select a team.')
            return redirect('player_clearance_dashboard')

        players = Player.objects.filter(
            team_id=team_id,
            huduma_status=HudumaVerificationStatus.NOT_CHECKED,
        )

        if not players.exists():
            messages.info(request, 'No unchecked players for this team.')
            return redirect('player_clearance_dashboard')

        svc = HudumaKenyaService()
        verified = 0
        failed = 0
        errors = 0

        for player in players:
            result = svc.verify_player_age(player)

            if result.is_verified:
                player.huduma_status = HudumaVerificationStatus.VERIFIED
                player.huduma_reference = result.reference_number
                player.huduma_notes = f"Bulk verified. Ref: {result.reference_number}"
                verified += 1
            elif result.success:
                player.huduma_status = HudumaVerificationStatus.FAILED
                player.huduma_notes = "Bulk check — verification failed."
                failed += 1
            else:
                player.huduma_status = HudumaVerificationStatus.PENDING
                player.huduma_notes = f"API error: {result.error_message}"
                errors += 1

            player.huduma_verified_at = timezone.now()
            player.huduma_verified_by = request.user
            player.save()

            PlayerVerificationLog.objects.create(
                player=player,
                step=VerificationStep.HUDUMA,
                action='bulk_check',
                result=player.huduma_status,
                details={
                    'reference': result.reference_number,
                    'person_found': result.person_found,
                },
                performed_by=request.user,
            )

        messages.success(
            request,
            f'Huduma Kenya bulk check complete: {verified} verified, '
            f'{failed} failed, {errors} errors.'
        )
        return redirect('player_clearance_dashboard')

    return redirect('player_clearance_dashboard')


# ══════════════════════════════════════════════════════════════════════════════
#   API ENDPOINT — FIFA Connect Player Quick-Check (AJAX)
# ══════════════════════════════════════════════════════════════════════════════

@login_required(login_url='web_login')
@require_POST
def api_fifa_connect_quick_check(request):
    """
    AJAX endpoint to quickly check a player name/ID against FIFA Connect
    during the player registration form. Returns JSON.
    """
    first_name = request.POST.get('first_name', '')
    last_name = request.POST.get('last_name', '')
    dob = request.POST.get('date_of_birth', '')
    national_id = request.POST.get('national_id', '')
    fifa_id = request.POST.get('fifa_connect_id', '')

    if not (first_name and last_name):
        return JsonResponse({'error': 'First name and last name are required.'}, status=400)

    svc = FIFAConnectService()
    result = svc.check_player_by_data(
        first_name=first_name,
        last_name=last_name,
        date_of_birth=dob,
        national_id=national_id,
        fifa_id=fifa_id,
    )

    return JsonResponse({
        'success': result.success,
        'player_found': result.player_found,
        'fifa_connect_id': result.fifa_connect_id,
        'is_flagged': result.is_flagged,
        'is_clear': result.is_clear,
        'flag_reason': result.flag_reason,
        'leagues_found': result.leagues_found,
        'error_message': result.error_message,
    })


@login_required(login_url='web_login')
@require_POST
def api_iprs_lookup(request):
    """
    AJAX endpoint — look up a person by National ID via IPRS.

    Called from the add-player form when the user enters a National ID number.
    Returns JSON with the person's name, date of birth, age, and gender so
    the form fields can be auto-populated.
    """
    national_id = request.POST.get('national_id', '').strip()

    if not national_id:
        return JsonResponse({'success': False, 'error_message': 'National ID is required.'}, status=400)

    # Basic format validation — Kenyan IDs are 7-8 digits
    if not national_id.isdigit() or len(national_id) < 7 or len(national_id) > 8:
        return JsonResponse({
            'success': False,
            'error_message': 'Invalid National ID format. Must be 7-8 digits.',
        }, status=400)

    svc = HudumaKenyaService()
    result = svc.lookup_by_national_id(national_id)

    return JsonResponse(result.to_dict())


@login_required(login_url='web_login')
def player_verification_logs(request, player_pk):
    """View full verification audit trail for a player."""
    player = get_object_or_404(Player, pk=player_pk)
    logs = PlayerVerificationLog.objects.filter(player=player).select_related('performed_by')

    return render(request, 'portal/player_verification_logs.html', {
        'player': player,
        'logs': logs,
    })
