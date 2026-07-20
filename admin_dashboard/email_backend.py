"""
Custom email backend that wraps the real SMTP backend and logs
every outgoing email to the EmailLog model.
"""
import re
import threading
from django.core.mail.backends.smtp import EmailBackend as SMTPBackend
from django.utils import timezone
from django.utils.html import strip_tags


def _clean_plain(text):
    """Strip <style>/<script> blocks then HTML tags to produce clean plain text."""
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    return strip_tags(text).strip()


class LoggingSMTPBackend(SMTPBackend):
    """Send email via SMTP and write a row to EmailLog."""

    def send_messages(self, email_messages):
        num_sent = super().send_messages(email_messages)
        threading.Thread(
            target=self._log_messages,
            args=(email_messages,),
            daemon=True,
        ).start()
        return num_sent

    @staticmethod
    def _log_messages(email_messages):
        try:
            from admin_dashboard.models import EmailLog

            for msg in email_messages:
                html_body = ''
                if hasattr(msg, 'alternatives'):
                    for content, mimetype in getattr(msg, 'alternatives', []):
                        if mimetype == 'text/html':
                            html_body = content
                            break

                # Use HTML body for plain text if available (cleaner output)
                plain = _clean_plain(html_body) if html_body else (msg.body or '')

                EmailLog.objects.create(
                    direction='OUT',
                    status='sent',
                    from_email=msg.from_email or '',
                    to_emails=', '.join(msg.to) if msg.to else '',
                    cc_emails=', '.join(msg.cc) if msg.cc else '',
                    bcc_emails=', '.join(msg.bcc) if msg.bcc else '',
                    subject=msg.subject or '',
                    body_text=plain,
                    body_html=html_body,
                    sent_at=timezone.now(),
                )
        except Exception:
            pass  # never break email delivery because of logging
