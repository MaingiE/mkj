"""
admin_dashboard/inbox_fetcher.py
Connects to IMAP (Namecheap Private Email) and pulls new messages
into EmailLog with direction='IN'.
"""
import imaplib
import email as email_lib
from email.header import decode_header
from email.utils import parsedate_to_datetime
import logging

from django.conf import settings
from django.utils import timezone

from .models import EmailLog

logger = logging.getLogger(__name__)


def _decode_header_value(raw):
    """Decode an RFC 2047 encoded header into a plain string."""
    if not raw:
        return ''
    parts = decode_header(raw)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or 'utf-8', errors='replace'))
        else:
            decoded.append(part)
    return ''.join(decoded)


def _get_body(msg):
    """Extract plain-text and HTML body from an email.message.Message."""
    text_body = ''
    html_body = ''

    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get('Content-Disposition', ''))
            if 'attachment' in disp:
                continue
            try:
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset() or 'utf-8'
                decoded = payload.decode(charset, errors='replace')
            except Exception:
                continue

            if ctype == 'text/plain' and not text_body:
                text_body = decoded
            elif ctype == 'text/html' and not html_body:
                html_body = decoded
    else:
        try:
            payload = msg.get_payload(decode=True)
            charset = msg.get_content_charset() or 'utf-8'
            decoded = payload.decode(charset, errors='replace') if payload else ''
        except Exception:
            decoded = ''

        if msg.get_content_type() == 'text/html':
            html_body = decoded
        else:
            text_body = decoded

    return text_body, html_body


def fetch_inbox(folder='INBOX', limit=50):
    """
    Connect to IMAP, fetch the latest `limit` messages from `folder`,
    and store any new ones (by Message-ID) as EmailLog(direction='IN').
    Returns (new_count, skipped_count).
    """
    host = getattr(settings, 'IMAP_HOST', '')
    port = getattr(settings, 'IMAP_PORT', 993)
    use_ssl = getattr(settings, 'IMAP_USE_SSL', True)
    user = getattr(settings, 'IMAP_USER', '')
    password = getattr(settings, 'IMAP_PASSWORD', '')

    if not host or not user or not password:
        raise ValueError('IMAP credentials not configured. Set IMAP_HOST, IMAP_USER, IMAP_PASSWORD.')

    if use_ssl:
        conn = imaplib.IMAP4_SSL(host, port)
    else:
        conn = imaplib.IMAP4(host, port)

    try:
        conn.login(user, password)
        conn.select(folder, readonly=True)

        # Search for all messages; take the last `limit`
        status, data = conn.search(None, 'ALL')
        if status != 'OK':
            raise RuntimeError(f'IMAP search failed: {status}')

        msg_nums = data[0].split()
        if not msg_nums:
            return 0, 0

        # Fetch only the newest `limit` messages
        recent = msg_nums[-limit:]

        # Pre-load existing message_ids to avoid DB queries per message
        existing_ids = set(
            EmailLog.objects.filter(
                direction='IN',
            ).values_list('message_id', flat=True)
        )
        # We need to fetch headers first to know message_ids, then bulk check
        # For efficiency, fetch all in one batch and deduplicate in Python

        new_count = 0
        skipped = 0

        # Fetch in batches of up to 25 to avoid oversized commands
        batch_size = 25
        for i in range(0, len(recent), batch_size):
            batch = recent[i:i + batch_size]
            batch_str = ','.join(n.decode() if isinstance(n, bytes) else str(n) for n in batch)

            status, msg_data = conn.fetch(batch_str, '(RFC822)')
            if status != 'OK':
                continue

            for response_part in msg_data:
                if not isinstance(response_part, tuple):
                    continue

                raw_email = response_part[1]
                msg = email_lib.message_from_bytes(raw_email)

                message_id = msg.get('Message-ID', '').strip()
                if not message_id:
                    continue

                # Skip if already imported
                if message_id in existing_ids:
                    skipped += 1
                    continue

                subject = _decode_header_value(msg.get('Subject', ''))
                from_addr = _decode_header_value(msg.get('From', ''))
                to_addr = _decode_header_value(msg.get('To', ''))
                cc_addr = _decode_header_value(msg.get('Cc', ''))

                # Parse date
                date_str = msg.get('Date', '')
                try:
                    sent_dt = parsedate_to_datetime(date_str)
                    if timezone.is_naive(sent_dt):
                        sent_dt = timezone.make_aware(sent_dt)
                except Exception:
                    sent_dt = timezone.now()

                text_body, html_body = _get_body(msg)

                EmailLog.objects.create(
                    direction='IN',
                    status='sent',
                    from_email=from_addr[:254],
                    to_emails=to_addr,
                    cc_emails=cc_addr,
                    subject=subject[:500],
                    body_text=text_body,
                    body_html=html_body,
                    sent_at=sent_dt,
                    message_id=message_id[:500],
                )
                existing_ids.add(message_id)
                new_count += 1

        return new_count, skipped

    finally:
        try:
            conn.close()
        except Exception:
            pass
        try:
            conn.logout()
        except Exception:
            pass
