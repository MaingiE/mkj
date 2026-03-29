"""
admin_dashboard/email_views.py - Email monitoring dashboard for admins.
Provides sent-mail log, detail view, and compose/send capability.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from .models import EmailLog


@staff_member_required
def fetch_inbox_view(request):
    """Trigger IMAP inbox fetch from the dashboard."""
    if request.method == 'POST':
        from .inbox_fetcher import fetch_inbox
        try:
            new, skipped = fetch_inbox(limit=100)
            if new:
                messages.success(request, f'Fetched {new} new email(s). ({skipped} already imported)')
            else:
                messages.info(request, f'Inbox is up to date. ({skipped} already imported)')
        except Exception as exc:
            messages.error(request, f'Inbox fetch failed: {exc}')
    return redirect('email_dashboard')


@staff_member_required
def email_dashboard(request):
    """List all sent/received emails with filters."""
    direction = request.GET.get('direction', '')
    search = request.GET.get('search', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    qs = EmailLog.objects.all()

    if direction:
        qs = qs.filter(direction=direction)
    if search:
        qs = qs.filter(
            Q(subject__icontains=search) |
            Q(to_emails__icontains=search) |
            Q(from_email__icontains=search) |
            Q(body_text__icontains=search)
        )
    if date_from:
        qs = qs.filter(sent_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(sent_at__date__lte=date_to)

    total = qs.count()
    today = qs.filter(sent_at__date=timezone.now().date()).count()
    inbox_count = EmailLog.objects.filter(direction='IN').count()
    outbox_count = EmailLog.objects.filter(direction='OUT').count()

    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'admin_dashboard/email_dashboard.html', {
        'page_obj': page_obj,
        'total': total,
        'today': today,
        'inbox_count': inbox_count,
        'outbox_count': outbox_count,
        'direction': direction,
        'search': search,
        'date_from': date_from,
        'date_to': date_to,
    })


@staff_member_required
def email_detail(request, email_id):
    """View a single email's full content."""
    email = get_object_or_404(EmailLog, pk=email_id)
    return render(request, 'admin_dashboard/email_detail.html', {
        'email': email,
    })


@staff_member_required
def email_compose(request):
    """Compose and send an email from info@mkjsupacup.com."""
    if request.method == 'POST':
        to_raw = request.POST.get('to', '').strip()
        cc_raw = request.POST.get('cc', '').strip()
        subject = request.POST.get('subject', '').strip()
        body = request.POST.get('body', '').strip()

        if not to_raw or not subject or not body:
            messages.error(request, 'To, Subject and Body are required.')
            return render(request, 'admin_dashboard/email_compose.html', {
                'to': to_raw, 'cc': cc_raw, 'subject': subject, 'body': body,
            })

        to_list = [e.strip() for e in to_raw.split(',') if e.strip()]
        cc_list = [e.strip() for e in cc_raw.split(',') if e.strip()]

        try:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=to_list,
                cc=cc_list,
            )
            msg.send()

            # If using the console backend (dev), log manually since
            # LoggingSMTPBackend won't be active.
            if 'console' in settings.EMAIL_BACKEND.lower():
                EmailLog.objects.create(
                    direction='OUT',
                    status='sent',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to_emails=', '.join(to_list),
                    cc_emails=', '.join(cc_list),
                    subject=subject,
                    body_text=body,
                    sent_at=timezone.now(),
                    sent_by=request.user,
                )

            messages.success(request, f'Email sent to {", ".join(to_list)}')
            return redirect('email_dashboard')
        except Exception as exc:
            EmailLog.objects.create(
                direction='OUT',
                status='failed',
                from_email=settings.DEFAULT_FROM_EMAIL,
                to_emails=', '.join(to_list),
                cc_emails=', '.join(cc_list),
                subject=subject,
                body_text=body,
                sent_at=timezone.now(),
                sent_by=request.user,
                error_message=str(exc),
            )
            messages.error(request, f'Send failed: {exc}')
            return render(request, 'admin_dashboard/email_compose.html', {
                'to': to_raw, 'cc': cc_raw, 'subject': subject, 'body': body,
            })

    return render(request, 'admin_dashboard/email_compose.html')
