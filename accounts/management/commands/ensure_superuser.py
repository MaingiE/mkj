"""
Management command: ensure_superuser
--------------------------------------
Creates an admin superuser from environment variables if one does not
already exist.  Safe to run on every deploy — it is a no-op when the
account is already present.

Required env vars:
    DJANGO_SUPERUSER_EMAIL
    DJANGO_SUPERUSER_PASSWORD

Optional env vars:
    DJANGO_SUPERUSER_FIRST_NAME  (default: "Admin")
    DJANGO_SUPERUSER_LAST_NAME   (default: "User")
    DJANGO_SUPERUSER_PHONE       (default: "0700000000")

Usage:
    python manage.py ensure_superuser          # reads from env vars
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create a superuser from env vars if one does not already exist."

    def handle(self, *args, **options):
        User = get_user_model()

        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "").strip()

        if not email or not password:
            self.stdout.write(self.style.WARNING(
                "DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD env vars "
                "not set — skipping superuser creation."
            ))
            return

        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.SUCCESS(
                f"Superuser '{email}' already exists — skipping."
            ))
            return

        User.objects.create_superuser(
            email=email,
            password=password,
            first_name=os.environ.get("DJANGO_SUPERUSER_FIRST_NAME", "Admin"),
            last_name=os.environ.get("DJANGO_SUPERUSER_LAST_NAME", "User"),
            phone=os.environ.get("DJANGO_SUPERUSER_PHONE", "0700000000"),
        )
        self.stdout.write(self.style.SUCCESS(
            f"✓ Superuser '{email}' created successfully."
        ))
