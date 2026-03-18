def seed_test_log():
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = User.objects.filter(is_superuser=True).first()
    if user:
        ActivityLog.objects.create(
            user=user,
            action='TEAM_APPROVE',
            description='Seeded test log for TEAM_APPROVE',
            ip_address='127.0.0.1',
            user_agent='seed-script',
            extra_data={}
        )
        print('Seeded test log.')
    else:
        print('No superuser found to seed log.')
# admin_dashboard/activity_logger.py
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from .models import ActivityLog

def log_activity(user, action, description, obj=None, ip_address=None, extra_data=None):
    """
    Log user activity to the database
    
    Args:
        user: User object performing the action
        action: Action type (e.g., 'CREATE', 'UPDATE', 'DELETE', 'LOGIN', 'APPROVE')
        description: Human-readable description of the action
        obj: Optional related object (Team, Match, Player, etc.)
        ip_address: User's IP address
        extra_data: Dictionary of additional data to store
    """
    activity = ActivityLog(
        user=user,
        action=action,
        description=description,
        ip_address=ip_address,
        extra_data=extra_data or {}
    )
    
    if obj:
        activity.content_type = ContentType.objects.get_for_model(obj)
        activity.object_id = obj.id
        activity.object_repr = str(obj)
    
    activity.save()
    return activity


def get_client_ip(request):
    """Get the client's IP address from the request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# Decorator for automatic logging
def log_action(action_type, description_template):
    """
    Decorator to automatically log actions
    
    Usage:
        @log_action('APPROVE', 'Approved team: {team.team_name}')
        def approve_team(request, team_id):
            team = Team.objects.get(id=team_id)
            team.status = 'approved'
            team.save()
            return redirect('...')
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            result = view_func(request, *args, **kwargs)
            
            # Try to format description with local variables
            try:
                local_vars = result.context_data if hasattr(result, 'context_data') else {}
                description = description_template.format(**local_vars)
            except:
                description = description_template
            
            log_activity(
                user=request.user,
                action=action_type,
                description=description,
                ip_address=get_client_ip(request)
            )
            
            return result
        return wrapper
    return decorator
