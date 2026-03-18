# admin_dashboard/middleware.py
from django.utils.deprecation import MiddlewareMixin
from .activity_logger import log_activity, get_client_ip


class ActivityLogMiddleware(MiddlewareMixin):
    """
    Middleware to automatically log certain user activities
    """
    
    def process_request(self, request):
        # Store IP in request for later use
        request.client_ip = get_client_ip(request)
        request.user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
        return None
    
    def process_response(self, request, response):
        # Log successful logins (status code 302 to redirect after login)
        if hasattr(request, 'user') and request.user.is_authenticated:
            # Check if this is a login action
            if request.path in ['/accounts/login/', '/admin/login/'] and response.status_code == 302:
                log_activity(
                    user=request.user,
                    action='LOGIN',
                    description=f'User logged in from {request.client_ip}',
                    ip_address=request.client_ip,
                    extra_data={'user_agent': request.user_agent}
                )
        
        return response
