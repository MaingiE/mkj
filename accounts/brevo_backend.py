"""
Brevo (Sendinblue) HTTP API Email Backend for Django.

Bypasses SMTP entirely - uses Brevo's transactional email REST API over HTTPS.
This works on Railway (and any platform) because HTTPS port 443 is never blocked.

Usage:
  1. Get your Brevo API key from: Settings → SMTP & API → API Keys
  2. Set in .env:
       EMAIL_BACKEND=accounts.brevo_backend.BrevoEmailBackend
       BREVO_API_KEY=xkeysib-your-api-key-here
       DEFAULT_FROM_EMAIL=MKJ SUPA CUP <info@mkjsupacup.com>
  3. Ensure info@mkjsupacup.com is verified as a sender in Brevo.

All existing Django mail calls (send_mail, EmailMultiAlternatives, etc.)
automatically route through this backend - zero code changes needed.
"""

import logging
import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


class BrevoEmailBackend(BaseEmailBackend):
    """
    Django email backend that sends via Brevo's HTTP API.
    Falls back to logging on failure (never crashes the request).
    """

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = getattr(settings, 'BREVO_API_KEY', '')

    def send_messages(self, email_messages):
        if not self.api_key:
            logger.error("BREVO_API_KEY is not set - emails will not be sent.")
            if not self.fail_silently:
                raise ValueError("BREVO_API_KEY is not configured.")
            return 0

        sent_count = 0
        for message in email_messages:
            try:
                if self._send_one(message):
                    sent_count += 1
            except Exception as exc:
                logger.error("Brevo API send failed for '%s': %s", message.subject, exc)
                if not self.fail_silently:
                    raise
        return sent_count

    def _send_one(self, message):
        """Send a single EmailMessage via Brevo HTTP API."""
        # Build recipient list
        to_list = [{"email": addr} for addr in message.to]
        if not to_list:
            return False

        # Parse sender
        from_email = message.from_email or getattr(
            settings, 'DEFAULT_FROM_EMAIL', 'info@mkjsupacup.com'
        )
        sender = self._parse_email(from_email)

        # Build payload
        payload = {
            "sender": sender,
            "to": to_list,
            "subject": message.subject,
            "textContent": message.body,
        }

        # Add CC/BCC if present
        if message.cc:
            payload["cc"] = [{"email": addr} for addr in message.cc]
        if message.bcc:
            payload["bcc"] = [{"email": addr} for addr in message.bcc]

        # Check for HTML alternative
        html_content = None
        if hasattr(message, 'alternatives'):
            for content, mimetype in message.alternatives:
                if mimetype == 'text/html':
                    html_content = content
                    break
        if html_content:
            payload["htmlContent"] = html_content

        # Add reply-to if set
        if message.reply_to:
            payload["replyTo"] = self._parse_email(message.reply_to[0])

        # Send via Brevo API
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "api-key": self.api_key,
        }

        response = requests.post(
            BREVO_API_URL,
            json=payload,
            headers=headers,
            timeout=15,
        )

        if response.status_code in (200, 201):
            logger.info(
                "✉ Brevo sent '%s' → %s (messageId: %s)",
                message.subject,
                [r["email"] for r in to_list],
                response.json().get("messageId", "?"),
            )
            return True
        else:
            logger.error(
                "✉ Brevo API error %d for '%s' → %s: %s",
                response.status_code,
                message.subject,
                [r["email"] for r in to_list],
                response.text,
            )
            if not self.fail_silently:
                response.raise_for_status()
            return False

    @staticmethod
    def _parse_email(email_str):
        """
        Parse 'Name <email@example.com>' into {"name": "Name", "email": "email@example.com"}.
        Also handles plain 'email@example.com'.
        """
        email_str = str(email_str).strip()
        if '<' in email_str and '>' in email_str:
            name = email_str[:email_str.index('<')].strip().strip('"')
            email = email_str[email_str.index('<') + 1:email_str.index('>')].strip()
            return {"name": name, "email": email} if name else {"email": email}
        return {"email": email_str}
