# admin_dashboard/activity_log.py
"""
Activity Logging and Undo System for FKF League Management
Tracks all administrative actions with the ability to undo/rollback changes
"""


def _perform_undo(log):
    """
    Internal function to perform the actual undo operation
    Returns (success, message)
    """
    from teams.models import Team, Player
    from matches.models import Match
    
    try:
        if log.action_type == 'team_approved':
            # Revert team to pending
            team = log.content_object
            if team and hasattr(team, 'status'):
                team.status = log.previous_state.get('status', 'pending')
                team.save()
                return True, f"Team {team.team_name} reverted to {team.status}"
        
        elif log.action_type == 'team_rejected':
            # Revert team to previous status
            team = log.content_object
            if team and hasattr(team, 'status'):
                team.status = log.previous_state.get('status', 'pending')
                team.save()
                return True, f"Team {team.team_name} status restored"
        
        elif log.action_type == 'fixtures_generated':
            # Delete generated fixtures
            from teams.models import Zone
            zone = log.content_object
            if zone:
                Match.objects.filter(zone=zone).delete()
                zone.fixtures_generated = False
                zone.fixture_generation_date = None
                zone.save()
                return True, f"Fixtures deleted for {zone.name}"
        
        elif log.action_type == 'player_suspended':
            # Lift suspension
            from matches.models import Suspension
            player = log.content_object
            if player:
                Suspension.objects.filter(player=player, is_active=True).update(is_active=False)
                return True, f"Suspension lifted for {player.full_name}"
        
        elif log.action_type == 'user_deactivated':
            # Reactivate user
            user_obj = log.content_object
            if user_obj and hasattr(user_obj, 'is_active'):
                user_obj.is_active = True
                user_obj.save()
                return True, f"User {user_obj.username} reactivated"
        
        elif log.action_type == 'transfer_approved':
            # Reverse transfer
            transfer = log.content_object
            if transfer and hasattr(transfer, 'status'):
                transfer.status = 'pending'
                transfer.save()
                # Restore player to original team
                if log.previous_state and 'player_team' in log.previous_state:
                    player = transfer.player
                    old_team_id = log.previous_state['player_team']
                    from teams.models import Team
                    old_team = Team.objects.get(id=old_team_id)
                    player.team = old_team
                    player.save()
                return True, f"Transfer reversed for {transfer.player.full_name}"
        
        # Add more undo handlers as needed
        
        return False, "Undo operation not implemented for this action type"
        
    except Exception as e:
        return False, f"Error performing undo: {str(e)}"
