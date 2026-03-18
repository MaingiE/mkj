# accounts/signals.py — Log login and logout events to ActivityLog
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver


def _get_ip(request):
    if request is None:
        return None
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    return xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    from admin_dashboard.models import ActivityLog

    ActivityLog.objects.create(
        user=user,
        action="LOGIN",
        description=f"{user.get_full_name()} ({user.email}) logged in",
        ip_address=_get_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:500] if request else "",
    )


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    from admin_dashboard.models import ActivityLog

    if user is None:
        return
    ActivityLog.objects.create(
        user=user,
        action="LOGOUT",
        description=f"{user.get_full_name()} ({user.email}) logged out",
        ip_address=_get_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:500] if request else "",
    )


@receiver(user_login_failed)
def on_login_failed(sender, credentials, request, **kwargs):
    from admin_dashboard.models import ActivityLog

    email = credentials.get("username", credentials.get("email", "unknown"))
    ActivityLog.objects.create(
        user=None,
        action="LOGIN",
        description=f"Failed login attempt for {email}",
        ip_address=_get_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:500] if request else "",
        extra_data={"failed": True, "email_attempted": email},
    )
