"""
Management command: test_email
-------------------------------
Sends a test email via the configured EMAIL_BACKEND to verify Brevo
(or any backend) is working correctly from Railway or any environment.

Usage:
    python manage.py test_email you@example.com
    python manage.py test_email you@example.com --subject "Custom Subject"

Use this from Railway's shell (Dashboard → your service → Shell) to
confirm BREVO_API_KEY, DNS records, and sender verification are all
working before live traffic depends on it.
"""

from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = "Send a test email to verify the email backend is working."

    def add_arguments(self, parser):
        parser.add_argument(
            "recipient",
            help="Email address to send the test message to.",
        )
        parser.add_argument(
            "--subject",
            default="MKJ SUPA CUP - Email Test",
            help="Subject line (default: 'MKJ SUPA CUP - Email Test')",
        )

    def handle(self, *args, **options):
        recipient = options["recipient"]
        subject   = options["subject"]
        backend   = settings.EMAIL_BACKEND
        from_email = settings.DEFAULT_FROM_EMAIL

        self.stdout.write(f"Backend    : {backend}")
        self.stdout.write(f"From       : {from_email}")
        self.stdout.write(f"To         : {recipient}")
        self.stdout.write(f"BREVO_KEY  : {'SET ✓' if getattr(settings, 'BREVO_API_KEY', '') else 'NOT SET ✗'}")
        self.stdout.write("")

        try:
            result = send_mail(
                subject=subject,
                message=(
                    "This is a test message from the MKJ SUPA CUP Competition Management System.\n\n"
                    f"Backend: {backend}\n"
                    f"From: {from_email}\n"
                    "If you received this, email delivery is working correctly."
                ),
                from_email=from_email,
                recipient_list=[recipient],
                fail_silently=False,
            )
            if result:
                self.stdout.write(self.style.SUCCESS(
                    f"✓ Test email sent successfully to {recipient} (send_mail returned {result})"
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f"⚠ send_mail returned 0 — email may not have been delivered. "
                    f"Check BREVO_API_KEY and sender verification."
                ))
        except Exception as exc:
            raise CommandError(f"✗ Email send failed: {exc}") from exc
