"""
MKJ SUPA CUP Accounts - Force Password Change Middleware

Redirects any authenticated user with `must_change_password=True`
to the password-change page.  The only pages they are allowed to
visit are the change-password page, logout, and static/media files.
"""
from django.shortcuts import redirect
from django.urls import reverse


# URL names the user may still visit while forced to change password
ALLOWED_URL_NAMES = {
    "force_change_password",
    "web_logout",
    "web_login",
}

# Prefixes that should never be blocked (static assets, API, admin)
ALLOWED_PATH_PREFIXES = (
    "/static/",
    "/media/",
    "/admin/",
    "/api/",
)

# Exact paths that must always be accessible during forced password change
ALLOWED_PATHS = {
    "/portal/force-change-password/",
    "/portal/logout/",
    "/portal/login/",
}


class AutoLogoutMiddleware:
    """
    Server-side inactivity check.  On every authenticated request,
    compare the current time with the session's ``_last_activity``
    timestamp.  If the gap exceeds ``settings.AUTO_LOGOUT_IDLE_MINUTES``
    (default 15), flush the session (logs the user out) and redirect
    to the login page.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        import time
        from django.conf import settings
        from django.contrib.auth import logout

        idle_limit = getattr(settings, "AUTO_LOGOUT_IDLE_MINUTES", 15) * 60

        if request.user.is_authenticated:
            now = time.time()
            last = request.session.get("_last_activity")
            if last is not None and (now - last) > idle_limit:
                logout(request)
                from django.shortcuts import redirect
                return redirect("web_login")
            request.session["_last_activity"] = now

        return self.get_response(request)


class ForcePasswordChangeMiddleware:
    """
    If request.user.must_change_password is True, redirect every page
    request to the force-change-password page until they set a new password.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and getattr(request.user, "must_change_password", False):
            # Allow the whitelisted path prefixes through
            if request.path.startswith(ALLOWED_PATH_PREFIXES):
                return self.get_response(request)

            # Allow exact whitelisted paths through
            if request.path in ALLOWED_PATHS:
                return self.get_response(request)

            # Allow whitelisted URL names through (fallback)
            current_url_name = getattr(request.resolver_match, "url_name", None)
            if current_url_name in ALLOWED_URL_NAMES:
                return self.get_response(request)

            return redirect("force_change_password")

        return self.get_response(request)
