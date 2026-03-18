"""
Auto-create a RefereeProfile whenever a User with role='referee' is saved.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
import uuid


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_referee_profile(sender, instance, **kwargs):
    if instance.role == "referee":
        from referees.models import RefereeProfile

        RefereeProfile.objects.get_or_create(
            user=instance,
            defaults={
                "license_number": f"REF-{uuid.uuid4().hex[:8].upper()}",
                "county": getattr(instance, "county", "") or "",
                "is_approved": instance.is_active,
            },
        )
