# admin_dashboard/undo_handlers.py
"""
Undo handlers for reversing administrative actions — MKJ SUPA CUP CMS
"""

from django.utils import timezone
from teams.models import Team, Player
from competitions.models import Competition, Fixture
from django.contrib.auth import get_user_model

User = get_user_model()


def log_activity(user, action, description, obj=None, previous_state=None,
                 new_state=None, can_undo=False, request=None):
    """Helper function to log activities with undo support."""
    from admin_dashboard.models import ActivityLog
    from django.contrib.contenttypes.models import ContentType

    log = ActivityLog(
        user=user,
        action=action,
        description=description,
        previous_state=previous_state,
        new_state=new_state,
        can_undo=can_undo
    )

    if obj:
        log.content_type = ContentType.objects.get_for_model(obj)
        log.object_id = obj.pk
        log.object_repr = str(obj)

    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            log.ip_address = x_forwarded_for.split(',')[0]
        else:
            log.ip_address = request.META.get('REMOTE_ADDR')
        log.user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]

    log.save()
    return log


# ---------------------------------------------------------------------------
# Individual undo handlers
# ---------------------------------------------------------------------------

def undo_team_approval(log):
    """Undo team approval."""
    try:
        team = Team.objects.get(pk=log.object_id)
        if team.status == 'registered':
            team.status = log.previous_state.get('status', 'pending')
            team.save()
            return True, f"Team '{team.name}' reverted to {team.status} status"
        return False, "Team status already changed"
    except Team.DoesNotExist:
        return False, "Team no longer exists"


def undo_team_rejection(log):
    """Undo team rejection."""
    try:
        team = Team.objects.get(pk=log.object_id)
        team.status = log.previous_state.get('status', 'pending')
        team.save()
        return True, f"Team '{team.name}' status restored to {team.status}"
    except Team.DoesNotExist:
        return False, "Team no longer exists"


def undo_team_suspension(log):
    """Undo team suspension."""
    try:
        team = Team.objects.get(pk=log.object_id)
        if team.status == 'suspended':
            team.status = log.previous_state.get('status', 'registered')
            team.save()
            return True, f"Team '{team.name}' suspension lifted"
        return False, "Team is not currently suspended"
    except Team.DoesNotExist:
        return False, "Team no longer exists"


def undo_fixtures_generation(log):
    """Undo fixture generation for a competition."""
    try:
        competition = Competition.objects.get(pk=log.object_id)
        fixtures = Fixture.objects.filter(competition=competition)
        played = fixtures.filter(status__in=['completed', 'in_progress']).count()

        if played > 0:
            return False, f"Cannot undo: {played} fixture(s) already played"

        count = fixtures.count()
        fixtures.delete()
        return True, f"Deleted {count} fixtures for '{competition.name}'"
    except Competition.DoesNotExist:
        return False, "Competition no longer exists"


def undo_player_suspension(log):
    """Undo player suspension."""
    try:
        player = Player.objects.get(pk=log.object_id)
        if player.status == 'suspended':
            player.status = log.previous_state.get('status', 'eligible')
            player.save()
            return True, f"Suspension lifted for '{player.first_name} {player.last_name}'"
        return False, "Player is not currently suspended"
    except Player.DoesNotExist:
        return False, "Player no longer exists"


def undo_user_deactivation(log):
    """Undo user deactivation."""
    try:
        user = User.objects.get(pk=log.object_id)
        if not user.is_active:
            user.is_active = True
            user.save()
            return True, f"User '{user.email}' reactivated"
        return False, "User is already active"
    except User.DoesNotExist:
        return False, "User no longer exists"


def undo_user_role_change(log):
    """Undo user role change."""
    try:
        user = User.objects.get(pk=log.object_id)
        prev_state = log.previous_state or {}

        if 'role' in prev_state:
            user.role = prev_state['role']

        if 'is_staff' in prev_state:
            user.is_staff = prev_state['is_staff']

        user.save()
        return True, f"User '{user.email}' role restored"
    except User.DoesNotExist:
        return False, "User no longer exists"


def undo_competition_assignment(log):
    """Undo competition assignment."""
    try:
        team = Team.objects.get(pk=log.object_id)
        prev_state = log.previous_state or {}
        if 'competition_id' in prev_state:
            old_comp_id = prev_state['competition_id']
            if old_comp_id:
                team.competition_id = old_comp_id
            else:
                team.competition = None
            team.save()
            comp_name = team.competition.name if team.competition else "None"
            return True, f"Team '{team.name}' competition restored to {comp_name}"
        return False, "Previous competition information not available"
    except Team.DoesNotExist:
        return False, "Team no longer exists"


# ---------------------------------------------------------------------------
# Undo handler registry
# ---------------------------------------------------------------------------
UNDO_HANDLERS = {
    'TEAM_APPROVE': undo_team_approval,
    'TEAM_REJECT': undo_team_rejection,
    'TEAM_SUSPEND': undo_team_suspension,
    'FIXTURE_GENERATE': undo_fixtures_generation,
    'FIXTURE_REGENERATE': undo_fixtures_generation,
    'SUSPENSION_CREATE': undo_player_suspension,
    'USER_DELETE': None,  # Cannot undo deletion
    'USER_ROLE_CHANGE': undo_user_role_change,
    'COMPETITION_ASSIGN': undo_competition_assignment,
}


def perform_undo(log, user, reason=""):
    """
    Perform undo operation.

    Args:
        log: ActivityLog instance to undo
        user: User performing the undo
        reason: Reason for undo

    Returns:
        (success, message) tuple
    """
    if not log.can_be_undone():
        return False, "This action cannot be undone (already undone, too old, or not undoable)"

    handler = UNDO_HANDLERS.get(log.action)

    if handler is None:
        return False, f"Undo not implemented for action type: {log.get_action_display()}"

    try:
        success, message = handler(log)

        if success:
            log.is_undone = True
            log.undone_at = timezone.now()
            log.undone_by = user
            log.undo_reason = reason
            log.save()

            log_activity(
                user=user,
                action='OTHER',
                description=f"Undid action: {log.description}. Reason: {reason}",
                obj=None,
                can_undo=False
            )

        return success, message

    except Exception as e:
        return False, f"Error during undo: {str(e)}"
