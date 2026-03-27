# admin_dashboard/activity_middleware.py
from django.utils.deprecation import MiddlewareMixin
from django.contrib.contenttypes.models import ContentType
from .models import ActivityLog
import json


class ActivityLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to automatically log user activities across the MKJ SUPA CUP CMS.
    Captures POST requests that change data and logs them as ActivityLog entries.
    Login/logout are handled by accounts.signals instead.
    """

    # Map URL fragments to action types
    LOGGED_PATHS = {
        # Team Management
        '/portal/teams/': 'TEAM_UPDATE',
        '/add-player/': 'PLAYER_CREATE',
        '/edit/': 'PLAYER_UPDATE',
        '/delete/': 'PLAYER_DELETE',

        # Approval workflows
        '/portal/teams/pending/': 'TEAM_APPROVE',
        '/portal/referees/pending/': 'REFEREE_APPROVE',

        # Squad & Match
        '/squad/': 'MATCHDAY_SQUAD_SUBMIT',
        '/report/': 'MATCH_REPORT',
        '/review/': 'MATCH_REPORT_APPROVE',

        # Referee
        '/portal/appointments/': 'REFEREE_ACTION',
        '/portal/referee/availability/': 'REFEREE_ACTION',

        # Treasurer
        '/portal/treasurer/teams/': 'PAYMENT_ACTION',

        # Admin Dashboard
        '/portal/admin-dashboard/generate-fixtures/': 'FIXTURE_GENERATE',
        '/portal/admin-dashboard/reschedule-fixtures/': 'MATCH_RESCHEDULE',
        '/portal/admin-dashboard/approve-registrations/': 'TEAM_APPROVE',
        '/portal/admin-dashboard/approve-reports/': 'MATCH_REPORT_APPROVE',
        '/portal/admin-dashboard/suspensions/': 'SUSPENSION_CREATE',
        '/portal/admin-dashboard/assign-zones/': 'ZONE_ASSIGN',
        '/portal/admin-dashboard/users/create/': 'USER_CREATE',
        '/portal/admin-dashboard/users/toggle/': 'USER_UPDATE',
        '/portal/admin-dashboard/users/reset-password/': 'PASSWORD_CHANGE',
        '/portal/admin-dashboard/users/edit-roles/': 'USER_ROLE_CHANGE',
        '/portal/admin-dashboard/users/delete/': 'USER_DELETE',
        '/portal/admin-dashboard/transfers/': 'PLAYER_TRANSFER',
        '/portal/admin-dashboard/toggle-registration/': 'REGISTRATION_TOGGLE',
        '/portal/admin-dashboard/activity-logs/': 'ADMIN_ACTION',

        # Profile & password
        '/portal/profile/change-password/': 'PASSWORD_CHANGE',
        '/portal/force-change-password/': 'PASSWORD_CHANGE',

        # Public registration
        '/register/team/': 'TEAM_CREATE',
        '/register/referee/': 'REFEREE_REGISTER',

        # Squad review (referee)
        '/portal/squads/': 'SQUAD_APPROVE',
    }
    
    def process_response(self, request, response):
        """Log activity after successful POST requests"""

        # Only log for authenticated users
        if not request.user.is_authenticated:
            return response

        # Only log POST requests (actions that change data)
        if request.method != 'POST':
            return response

        # Only log successful responses (200-399)
        if not (200 <= response.status_code < 400):
            return response

        # Skip login/logout - handled by signals
        if any(seg in request.path for seg in ('/login/', '/logout/')):
            return response

        # Get the action type based on path
        action = self._get_action_type(request.path)
        if not action:
            return response
        
        # Get description
        description = self._generate_description(request, action)
        
        # Get IP address
        ip_address = self._get_client_ip(request)
        
        # Get user agent
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
        
        # Create activity log
        try:
            ActivityLog.objects.create(
                user=request.user,
                action=action,
                description=description,
                ip_address=ip_address,
                user_agent=user_agent,
                changes_json=self._get_changes_json(request)
            )
        except Exception as e:
            # Don't break the request if logging fails
            print(f"Activity logging error: {e}")
        
        return response
    
    def _get_action_type(self, path):
        """Determine action type from request path (most-specific match wins)."""
        best_match = None
        best_len = 0
        for pattern, action in self.LOGGED_PATHS.items():
            if pattern in path and len(pattern) > best_len:
                best_match = action
                best_len = len(pattern)
        return best_match

    def _generate_description(self, request, action):
        """Generate human-readable description of the action"""
        user = request.user
        name = user.get_full_name() or user.email
        path = request.path

        descriptions = {
            'FIXTURE_GENERATE': f'{name} generated fixtures',
            'FIXTURE_REGENERATE': f'{name} regenerated fixtures',
            'SQUAD_APPROVE': f'{name} approved matchday squad',
            'MATCHDAY_SQUAD_SUBMIT': f'{name} submitted matchday squad',
            'MATCH_REPORT': f'{name} submitted/updated match report',
            'MATCH_REPORT_APPROVE': f'{name} reviewed a match report',
            'TEAM_CREATE': f'{name} registered a new team',
            'TEAM_UPDATE': f'{name} updated team information',
            'TEAM_APPROVE': f'{name} approved/rejected a team',
            'PLAYER_CREATE': f'{name} added a new player',
            'PLAYER_UPDATE': f'{name} updated player information',
            'PLAYER_DELETE': f'{name} deleted a player',
            'PLAYER_TRANSFER': f'{name} processed player transfer',
            'MATCH_RESCHEDULE': f'{name} rescheduled a match',
            'REFEREE_REGISTER': f'{name} registered as referee',
            'REFEREE_APPROVE': f'{name} approved/rejected a referee',
            'REFEREE_ACTION': f'{name} performed referee action',
            'PAYMENT_ACTION': f'{name} processed payment/treasurer action',
            'ZONE_ASSIGN': f'{name} assigned team to competition/zone',
            'SQUAD_APPROVE': f'{name} reviewed a squad submission',
            'USER_CREATE': f'{name} created a new user account',
            'USER_UPDATE': f'{name} updated a user account',
            'USER_DELETE': f'{name} deleted a user account',
            'USER_ROLE_CHANGE': f'{name} changed a user role',
            'PASSWORD_CHANGE': f'{name} changed/reset a password',
            'SUSPENSION_CREATE': f'{name} managed a suspension',
            'REGISTRATION_TOGGLE': f'{name} toggled registration window',
        }

        return descriptions.get(action, f'{name} performed {action} at {path}')
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip[:45]  # Max length of IP field
    
    def _get_changes_json(self, request):
        """Extract relevant data from POST request"""
        try:
            # Get POST data (excluding sensitive fields)
            sensitive_fields = ['password', 'csrfmiddlewaretoken', 'password1', 'password2']
            data = {
                key: value for key, value in request.POST.items()
                if key not in sensitive_fields and not key.startswith('_')
            }
            
            # Limit size
            data_str = json.dumps(data, default=str)
            if len(data_str) > 5000:
                return json.dumps({'note': 'Data too large to store'})
            
            return data_str
        except Exception:
            return '{}'
