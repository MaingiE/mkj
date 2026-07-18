"""
Management command: test_email_backend
-----------------------------------------
Diagnoses why the configured EMAIL_BACKEND (typically
accounts.brevo_backend.BrevoEmailBackend) might be failing to import or
send email, and optionally sends a real test email.

Usage:
    python manage.py test_email_backend
    python manage.py test_email_backend --to someone@example.com
    python manage.py test_email_backend --to someone@example.com --send
"""

import importlib
import sys

from django.conf import settings
from django.core.mail import get_connection
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Test that the configured email backend (e.g. "
        "accounts.brevo_backend.BrevoEmailBackend) imports correctly and, "
        "optionally, that it can actually send an email."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            dest="to",
            default=None,
            help="Recipient email address to send a test email to.",
        )
        parser.add_argument(
            "--send",
            action="store_true",
            help="Actually send a test email (requires --to). Without this "
                 "flag, the command only runs import/connectivity checks.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("1. Checking EMAIL_BACKEND setting"))
        backend_path = getattr(settings, "EMAIL_BACKEND", None)
        if not backend_path:
            raise CommandError("EMAIL_BACKEND is not set in settings.")
        self.stdout.write(f"   EMAIL_BACKEND = {backend_path}")

        self.stdout.write(self.style.MIGRATE_HEADING("2. Checking 'requests' library"))
        try:
            import requests
            self.stdout.write(self.style.SUCCESS(
                f"   OK - requests {requests.__version__} is importable."
            ))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(
                f"   FAILED to import 'requests': {exc.__class__.__name__}: {exc}"
            ))
            self.stdout.write(
                "   -> Make sure 'requests' is listed in requirements.txt "
                "and installed in this environment."
            )

        self.stdout.write(self.style.MIGRATE_HEADING(
            "3. Checking accounts.brevo_backend module import"
        ))
        try:
            module = importlib.import_module("accounts.brevo_backend")
            importlib.reload(module)  # force re-execution to surface any load-time errors
        except Exception as exc:
            self.stdout.write(self.style.ERROR(
                f"   FAILED to import accounts.brevo_backend: "
                f"{exc.__class__.__name__}: {exc}"
            ))
            self.stderr.write(str(exc))
            raise CommandError(
                "accounts.brevo_backend failed to import. See error above/logs "
                "for the root cause."
            )
        else:
            self.stdout.write(self.style.SUCCESS(
                "   OK - accounts.brevo_backend imported successfully."
            ))
            if getattr(module, "_import_error", None):
                self.stdout.write(self.style.WARNING(
                    f"   WARNING - module loaded but 'requests' import "
                    f"previously failed: {module._import_error}"
                ))

        self.stdout.write(self.style.MIGRATE_HEADING(
            "4. Checking BrevoEmailBackend class is defined"
        ))
        if not hasattr(module, "BrevoEmailBackend"):
            raise CommandError(
                'Module "accounts.brevo_backend" does not define a '
                '"BrevoEmailBackend" class. Check the traceback above '
                "for the underlying import error."
            )
        self.stdout.write(self.style.SUCCESS(
            "   OK - BrevoEmailBackend class is defined."
        ))

        self.stdout.write(self.style.MIGRATE_HEADING("5. Checking BREVO_API_KEY setting"))
        api_key = getattr(settings, "BREVO_API_KEY", "")
        if not api_key:
            self.stdout.write(self.style.ERROR(
                "   BREVO_API_KEY is not set - emails will fail to send."
            ))
        else:
            masked = api_key[:6] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
            self.stdout.write(self.style.SUCCESS(f"   OK - BREVO_API_KEY is set ({masked})."))

        self.stdout.write(self.style.MIGRATE_HEADING("6. Instantiating email connection"))
        try:
            connection = get_connection()
            self.stdout.write(self.style.SUCCESS(
                f"   OK - connection instantiated: {connection.__class__.__module__}."
                f"{connection.__class__.__name__}"
            ))
        except Exception as exc:
            raise CommandError(
                f"Failed to instantiate email connection: "
                f"{exc.__class__.__name__}: {exc}"
            )

        to_address = options.get("to")
        should_send = options.get("send")

        if not to_address:
            self.stdout.write(self.style.SUCCESS(
                "\nAll diagnostic checks passed. Pass --to <email> --send to "
                "send a real test email."
            ))
            return

        if not should_send:
            self.stdout.write(self.style.WARNING(
                f"\n--to {to_address} given without --send: not sending an "
                "email. Add --send to actually deliver a test message."
            ))
            return

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"7. Sending test email to {to_address}"
        ))
        try:
            from django.core.mail import EmailMultiAlternatives

            email = EmailMultiAlternatives(
                subject="Test email from test_email_backend management command",
                body="This is a plain-text test email to verify the Brevo "
                     "email backend is working correctly.",
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                to=[to_address],
                connection=connection,
            )
            sent_count = email.send(fail_silently=False)
        except Exception as exc:
            raise CommandError(
                f"Failed to send test email: {exc.__class__.__name__}: {exc}"
            )

        if sent_count:
            self.stdout.write(self.style.SUCCESS(
                f"   OK - test email sent to {to_address}."
            ))
        else:
            self.stdout.write(self.style.ERROR(
                "   Send returned 0 - email was not sent. Check logs above."
            ))
            sys.exit(1)
