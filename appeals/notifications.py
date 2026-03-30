"""
MKJ SUPA CUP Appeals - Email Notification System

Sends email notifications to affected parties for:
1. Appeal submission - respondent team manager
2. Hearing schedule - both team managers
3. Decision published - both team managers
"""
import logging
from django.conf import settings
from django.core.mail import send_mail
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

SITE_URL = getattr(settings, 'SITE_URL', 'https://mkjsupacup.com')


def _appeals_base_html(title, body_content):
    """Branded HTML email template for appeals - matches main CMS design."""
    logo_base = f"{SITE_URL}/static/img"
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f0f2f5; margin: 0; padding: 0; }}
.wrap {{ max-width: 600px; margin: 0 auto; background: #fff; border-radius: 12px; overflow: hidden;
         box-shadow: 0 4px 24px rgba(0,0,0,.08); }}
.logo-bar {{ background: #fff; padding: 20px 32px; text-align: center; border-bottom: 1px solid #e8edf5; }}
.logo-bar img {{ height: 56px; margin: 0 12px; vertical-align: middle; }}
.header {{ background: linear-gradient(135deg, #1a237e 0%, #283593 50%, #3949ab 100%);
           padding: 28px 32px; text-align: center; }}
.header h1 {{ color: #fff; margin: 0; font-size: 16px; letter-spacing: 0.5px; font-weight: 600; line-height: 1.5; }}
.header p {{ color: rgba(255,255,255,.75); margin: 8px 0 0; font-size: 12px; }}
.body {{ padding: 32px; color: #333; line-height: 1.7; font-size: 14px; }}
.body h2 {{ color: #1a237e; margin: 0 0 20px; font-size: 18px; font-weight: 700; }}
table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
table td {{ padding: 10px; border-bottom: 1px solid #e8edf5; font-size: 14px; }}
.footer {{ background: #f8f9fb; padding: 24px 32px; text-align: center; font-size: 11px; color: #888;
           border-top: 1px solid #e8edf5; }}
.footer p {{ margin: 4px 0; }}
.footer .sign-off {{ font-weight: 600; color: #1a237e; font-size: 12px; margin-bottom: 8px; }}
</style></head><body>
<div style="padding:20px 0;">
<div class="wrap">
 <div class="logo-bar">
  <img src="{logo_base}/makueni_logo.png" alt="Makueni County" style="height:56px;">
  <img src="{logo_base}/TINA.jpeg" alt="Tina" style="height:56px;">
 </div>
 <div class="header">
  <h1>MKJ SUPA CUP Appeals System</h1>
  <p>Makueni County Sports Department</p>
 </div>
 <div class="body">
  <h2>{title}</h2>
  {body_content}
 </div>
 <div class="footer">
  <p class="sign-off">MKJ SUPA CUP Administration</p>
  <p style="font-size:12px;color:#555;margin:6px 0;">&#128222; 0700 000 000 &nbsp;|&nbsp; Reply to: <a href="mailto:info@mkjsupacup.com" style="color:#1a237e;text-decoration:none;">info@mkjsupacup.com</a></p>
  <p>&copy; 2026 MKJ SUPA CUP - Makueni County Sports Department</p>
  <p><a href="{SITE_URL}" style="color:#1a237e;text-decoration:none;">{SITE_URL}</a></p>
 </div>
</div>
</div>
</body></html>"""


def _get_team_manager_email(team):
    """Get the email of the team's manager, or None."""
    if team.manager and team.manager.email:
        return team.manager.email
    return None


def _safe_send(subject, html_message, recipient_list, fail_silently=True):
    """Send an email, logging errors instead of crashing."""
    plain_message = strip_tags(html_message)
    recipient_list = [e for e in recipient_list if e]
    if not recipient_list:
        logger.warning("No valid recipients for email: %s", subject)
        return False
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=fail_silently,
        )
        logger.info("Email sent: '%s' to %s", subject, recipient_list)
        return True
    except Exception as exc:
        logger.error("Failed to send email '%s': %s", subject, exc)
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  1. APPEAL SUBMITTED → Notify respondent team
# ══════════════════════════════════════════════════════════════════════════════

def notify_appeal_submitted(appeal):
    """
    Notify the respondent team manager that an appeal has been filed
    against their team and a response is required.
    """
    respondent_email = _get_team_manager_email(appeal.respondent_team)
    appellant_email = _get_team_manager_email(appeal.appellant_team)

    # Format the deadline
    deadline_str = ""
    if appeal.response_deadline:
        deadline_str = appeal.response_deadline.strftime("%d %b %Y at %H:%M")

    # Determine deadline context
    if appeal.match and hasattr(appeal.match, 'status') and appeal.match.status == 'live':
        deadline_context = (
            "Since the related match is currently ongoing, your response is due "
            "within 30 minutes after the match ends."
        )
    else:
        deadline_context = (
            "Your response is due within 30 minutes of this appeal being lodged."
        )

    subject = f"[MKJ SUPA CUP] Appeal #{appeal.pk} Filed Against {appeal.respondent_team.name}"

    body = f"""
    <p>An appeal has been filed against <strong>{appeal.respondent_team.name}</strong>.</p>
    <table>
        <tr><td><strong>Subject:</strong></td><td>{appeal.subject}</td></tr>
        <tr><td><strong>Filed By:</strong></td><td>{appeal.appellant_team.name}</td></tr>
        <tr><td><strong>Competition:</strong></td><td>{appeal.competition or 'N/A'}</td></tr>
        <tr><td><strong>Response Deadline:</strong></td>
            <td style="color: #dc3545; font-weight: bold;">{deadline_str}</td></tr>
    </table>
    <p style="background: #fff3cd; padding: 12px; border-radius: 6px; border-left: 4px solid #ffc107;">
        {deadline_context}
    </p>
    <p>Please log in to the MKJ SUPA CUP CMS to review the appeal and submit your response with supporting evidence.</p>
    """
    _safe_send(subject, _appeals_base_html(f"Appeal #{appeal.pk} - Response Required", body), [respondent_email])

    # Also notify the appellant that appeal was received
    appellant_subject = f"[MKJ SUPA CUP] Your Appeal #{appeal.pk} Has Been Submitted"
    appellant_body = f"""
    <p>Your appeal against <strong>{appeal.respondent_team.name}</strong> has been submitted.</p>
    <table>
        <tr><td><strong>Subject:</strong></td><td>{appeal.subject}</td></tr>
        <tr><td><strong>Against:</strong></td><td>{appeal.respondent_team.name}</td></tr>
        <tr><td><strong>Response Deadline:</strong></td><td>{deadline_str}</td></tr>
    </table>
    <p>The respondent team has been notified. You will receive further updates as the appeal progresses.</p>
    """
    _safe_send(appellant_subject, _appeals_base_html(f"Appeal #{appeal.pk} - Submitted Successfully", appellant_body), [appellant_email])


# ══════════════════════════════════════════════════════════════════════════════
#  2. HEARING SCHEDULED → Notify both teams
# ══════════════════════════════════════════════════════════════════════════════

def notify_hearing_scheduled(hearing):
    """
    Notify both team managers that a hearing has been scheduled for the appeal.
    """
    appeal = hearing.appeal
    appellant_email = _get_team_manager_email(appeal.appellant_team)
    respondent_email = _get_team_manager_email(appeal.respondent_team)

    hearing_dt = hearing.hearing_date.strftime("%d %b %Y")
    hearing_tm = hearing.hearing_time.strftime("%H:%M")
    location_text = hearing.location or "To be confirmed"

    subject = f"[MKJ SUPA CUP] Hearing Scheduled - Appeal #{appeal.pk}"

    body = f"""
    <p>The Chair of the Jury has scheduled a hearing for this appeal.</p>
    <table>
        <tr><td><strong>Appeal:</strong></td><td>#{appeal.pk} - {appeal.subject}</td></tr>
        <tr><td><strong>Appellant:</strong></td><td>{appeal.appellant_team.name}</td></tr>
        <tr><td><strong>Respondent:</strong></td><td>{appeal.respondent_team.name}</td></tr>
        <tr style="background: #e3f2fd;"><td><strong>Hearing Date:</strong></td><td style="font-weight: bold;">{hearing_dt}</td></tr>
        <tr style="background: #e3f2fd;"><td><strong>Hearing Time:</strong></td><td style="font-weight: bold;">{hearing_tm}</td></tr>
        <tr style="background: #e3f2fd;"><td><strong>Location:</strong></td><td style="font-weight: bold;">{location_text}</td></tr>
    </table>
    {"<p><strong>Notes:</strong> " + hearing.notes + "</p>" if hearing.notes else ""}
    <p style="background: #e8f5e9; padding: 12px; border-radius: 6px; border-left: 4px solid #4caf50;">
        Both teams are required to attend. Please ensure your representatives are available at the scheduled date and time.
    </p>
    """

    _safe_send(subject, _appeals_base_html(f"Hearing Scheduled - Appeal #{appeal.pk}", body), [appellant_email, respondent_email])


# ══════════════════════════════════════════════════════════════════════════════
#  3. DECISION PUBLISHED → Notify both teams
# ══════════════════════════════════════════════════════════════════════════════

def notify_decision_published(decision):
    """
    Notify both team managers that a jury decision has been published.
    Includes fee refund info (successful) or re-appeal window (rejected).
    """
    from .models import REAPPEAL_FEE_KES, REAPPEAL_WINDOW_MINUTES

    appeal = decision.appeal
    appellant_email = _get_team_manager_email(appeal.appellant_team)
    respondent_email = _get_team_manager_email(appeal.respondent_team)

    outcome_display = decision.get_outcome_display()
    outcome_color = (
        "#28a745" if decision.outcome == "successful"
        else "#dc3545" if decision.outcome == "rejected"
        else "#ffc107"
    )

    # Build conditional sections
    fee_refund_html = ""
    if decision.outcome == "successful":
        fee_refund_html = (
            f"<p style='background: #e8f5e9; padding: 12px; border-radius: 4px; border-left: 4px solid #4caf50;'>"
            f"💰 The appeal fee of KES {appeal.fee_amount:,.0f} will be refunded to the appellant.</p>"
        )

    reappeal_html = ""
    if decision.outcome == "rejected" and not appeal.is_reappeal:
        reappeal_html = (
            f"<p style='background: #fce4ec; padding: 12px; border-radius: 4px; border-left: 4px solid #e91e63;'>"
            f"⏱️ The appellant has <strong>{REAPPEAL_WINDOW_MINUTES} minutes</strong> from this notification "
            f"to file a re-appeal. Re-appeal fee is KES {REAPPEAL_FEE_KES:,}. "
            f"This is the final opportunity to challenge this decision.</p>"
        )

    subject = f"[MKJ SUPA CUP] Decision Published - Appeal #{appeal.pk}: {outcome_display}"

    body = f"""
    <p>The Chair of the Jury has published a decision on this appeal.</p>
    <table>
        <tr><td><strong>Appeal:</strong></td><td>#{appeal.pk} - {appeal.subject}</td></tr>
        <tr><td><strong>Appellant:</strong></td><td>{appeal.appellant_team.name}</td></tr>
        <tr><td><strong>Respondent:</strong></td><td>{appeal.respondent_team.name}</td></tr>
        <tr><td><strong>Outcome:</strong></td>
            <td><span style="background: {outcome_color}; color: #fff; padding: 4px 12px; border-radius: 4px; font-weight: bold;">{outcome_display}</span></td></tr>
    </table>
    <div style="background: #fff; padding: 15px; border-radius: 6px; border: 1px solid #e8edf5; margin: 15px 0;">
        <h4 style="margin: 0 0 8px; color: #1a237e;">Reasoning:</h4>
        <p style="margin: 0; white-space: pre-wrap;">{decision.reasoning}</p>
    </div>
    {"<div style='background: #fff3cd; padding: 15px; border-radius: 6px; border: 1px solid #ffc107; margin: 15px 0;'><h4 style='margin: 0 0 8px;'>Sanctions / Remedies:</h4><p style='margin: 0;'>" + decision.sanctions + "</p></div>" if decision.sanctions else ""}
    {fee_refund_html}
    {reappeal_html}
    <p>Log in to the MKJ SUPA CUP CMS for full details and evidence.</p>
    """

    _safe_send(subject, _appeals_base_html(f"Decision Published - Appeal #{appeal.pk}", body), [appellant_email, respondent_email])


# ══════════════════════════════════════════════════════════════════════════════
#  4. RESPONSE SUBMITTED → Notify appellant team
# ══════════════════════════════════════════════════════════════════════════════

def notify_response_submitted(appeal):
    """Notify the appellant team that the respondent has submitted a response."""
    appellant_email = _get_team_manager_email(appeal.appellant_team)

    subject = f"[MKJ SUPA CUP] Response Received - Appeal #{appeal.pk}"

    body = f"""
    <p><strong>{appeal.respondent_team.name}</strong> has submitted a response to your appeal.</p>
    <table>
        <tr><td><strong>Appeal:</strong></td><td>#{appeal.pk} - {appeal.subject}</td></tr>
        <tr><td><strong>Status:</strong></td><td>Response Received - Awaiting Jury Review</td></tr>
    </table>
    <p>The appeal will now proceed to the Chair of the Jury for review and determination.</p>
    <p>Log in to the MKJ SUPA CUP CMS to view the full response and evidence.</p>
    """

    _safe_send(subject, _appeals_base_html(f"Response Received - Appeal #{appeal.pk}", body), [appellant_email])


# ══════════════════════════════════════════════════════════════════════════════
#  5. RE-APPEAL FILED → Notify respondent team + jury chair
# ══════════════════════════════════════════════════════════════════════════════

def notify_reappeal_filed(appeal):
    """Notify both parties and jury chair that a re-appeal has been filed."""
    from .models import REAPPEAL_FEE_KES
    from accounts.models import User, UserRole

    respondent_email = _get_team_manager_email(appeal.respondent_team)
    appellant_email = _get_team_manager_email(appeal.appellant_team)

    # Also notify jury chair(s)
    jury_emails = list(
        User.objects.filter(role=UserRole.JURY_CHAIR, is_active=True)
        .values_list('email', flat=True)
    )

    subject = f"[MKJ SUPA CUP] Re-Appeal Filed - Appeal #{appeal.pk}"

    body = f"""
    <p><strong>{appeal.appellant_team.name}</strong> has filed a re-appeal against <strong>{appeal.respondent_team.name}</strong>.</p>
    <table>
        <tr><td><strong>Subject:</strong></td><td>{appeal.subject}</td></tr>
        <tr><td><strong>Original Appeal:</strong></td><td>#{appeal.original_appeal_id}</td></tr>
        <tr><td><strong>Re-Appeal Fee:</strong></td><td>KES {REAPPEAL_FEE_KES:,}</td></tr>
    </table>
    <p style="background: #fff3cd; padding: 12px; border-radius: 6px; border-left: 4px solid #ffc107;">
        This is a re-appeal. The decision on this re-appeal will be <strong>final and binding</strong>.
        The respondent team has 30 minutes to submit a response once the appeal is formally submitted.
    </p>
    <p>Log in to the MKJ SUPA CUP CMS for full details.</p>
    """

    all_recipients = [respondent_email, appellant_email] + jury_emails
    _safe_send(subject, _appeals_base_html(f"Re-Appeal Filed - Appeal #{appeal.pk}", body), all_recipients)


# ══════════════════════════════════════════════════════════════════════════════
#  6. FEE NOTIFICATIONS → Notify appellant
# ══════════════════════════════════════════════════════════════════════════════

def notify_fee_verified(appeal):
    """Notify appellant that their fee payment has been verified."""
    appellant_email = _get_team_manager_email(appeal.appellant_team)
    subject = f"[MKJ SUPA CUP] Appeal Fee Verified - Appeal #{appeal.pk}"
    body = f"""
    <p>Your appeal fee payment of <strong>KES {appeal.fee_amount:,.0f}</strong> has been verified.</p>
    <p>Reference: <strong>{appeal.fee_reference}</strong></p>
    <p style="background: #e8f5e9; padding: 12px; border-radius: 6px; border-left: 4px solid #4caf50;">
        You can now finalize and submit your appeal. Remember: the appeal fee is
        <strong>refundable only if the appeal is successful</strong>.
    </p>
    <p>Log in to the MKJ SUPA CUP CMS to submit your appeal.</p>
    """
    _safe_send(subject, _appeals_base_html(f"Fee Payment Verified - Appeal #{appeal.pk}", body), [appellant_email])


def notify_fee_rejected(appeal):
    """Notify appellant that their fee payment was rejected."""
    appellant_email = _get_team_manager_email(appeal.appellant_team)
    subject = f"[MKJ SUPA CUP] Appeal Fee Rejected - Appeal #{appeal.pk}"
    body = f"""
    <p>Your appeal fee payment for appeal <strong>#{appeal.pk}</strong> has been rejected.</p>
    <p style="background: #fce4ec; padding: 12px; border-radius: 6px; border-left: 4px solid #e91e63;">
        Please resubmit a valid M-Pesa or bank reference for KES {appeal.fee_amount:,.0f}.
    </p>
    <p>Log in to the MKJ SUPA CUP CMS to resubmit your payment reference.</p>
    """
    _safe_send(subject, _appeals_base_html(f"Fee Payment Rejected - Appeal #{appeal.pk}", body), [appellant_email])


def notify_fee_refunded(appeal):
    """Notify appellant that their fee has been refunded."""
    appellant_email = _get_team_manager_email(appeal.appellant_team)
    subject = f"[MKJ SUPA CUP] Appeal Fee Refunded - Appeal #{appeal.pk}"
    body = f"""
    <p>Your appeal fee of <strong>KES {appeal.fee_amount:,.0f}</strong> for appeal <strong>#{appeal.pk}</strong>
    has been marked for refund.</p>
    <p>Reference: <strong>{appeal.fee_reference}</strong></p>
    <p style="background: #e8f5e9; padding: 12px; border-radius: 6px; border-left: 4px solid #4caf50;">
        The refund will be processed to the original payment method. Please allow 2-3 business days.
    </p>
    """
    _safe_send(subject, _appeals_base_html(f"Fee Refunded - Appeal #{appeal.pk}", body), [appellant_email])


# ══════════════════════════════════════════════════════════════════════════════
#  7. HEARING CANCELLED → Notify both teams
# ══════════════════════════════════════════════════════════════════════════════

def notify_hearing_cancelled(hearing):
    """Notify both team managers that a hearing has been cancelled."""
    appeal = hearing.appeal
    appellant_email = _get_team_manager_email(appeal.appellant_team)
    respondent_email = _get_team_manager_email(appeal.respondent_team)

    hearing_dt = hearing.hearing_date.strftime("%d %b %Y")
    hearing_tm = hearing.hearing_time.strftime("%H:%M")

    subject = f"[MKJ SUPA CUP] Hearing Cancelled - Appeal #{appeal.pk}"
    body = f"""
    <p>The hearing scheduled for <strong>{hearing_dt} at {hearing_tm}</strong> has been cancelled.</p>
    <table>
        <tr><td><strong>Appeal:</strong></td><td>#{appeal.pk} - {appeal.subject}</td></tr>
    </table>
    <p>A new hearing may be scheduled. Check the MKJ SUPA CUP CMS for updates.</p>
    """
    _safe_send(subject, _appeals_base_html(f"Hearing Cancelled - Appeal #{appeal.pk}", body), [appellant_email, respondent_email])
