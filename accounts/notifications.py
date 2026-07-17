"""
MKJ SUPA CUP - Centralized Email + WhatsApp Notification System

Sends HTML emails for:
  1. Account creation (welcome + credentials)
  2. New player registered → subcounty officer, verification officer
  3. Fixture created/updated → team managers, subcounty officers
  4. Player verification needed → verification officer
  5. Squad submitted → coordinator
  6. Match report submitted → coordinator
  7. Team registration → admin, subcounty officer

WhatsApp notifications (via Brevo WhatsApp API):
  - Account credentials to new users on approval

All notifications are dispatched on background daemon threads so they
never block the web request — timeouts / API errors only appear in logs.
"""
import logging
import threading
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

SITE_URL = getattr(settings, 'SITE_URL', 'https://mkjsupacup.com')
FROM_EMAIL = getattr(settings, 'DEFAULT_FROM_EMAIL', 'MKJ SUPA CUP <admin@mkjsupacup.com>')
LIGI_FROM_EMAIL = getattr(settings, 'LIGI_FROM_EMAIL', 'Ligi Mashinani <ligimashinani@mkjsupacup.com>')


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _send(subject, html_body, recipients, fail_silently=True, from_email=None):
    """
    Send an HTML email on a background daemon thread.
    Returns immediately - never blocks the web request.
    Filters out blank addresses.  Retries up to 3 times on transient errors.
    Use from_email to override the sender (e.g. LIGI_FROM_EMAIL for ward TM mails).
    """
    recipients = [r for r in (recipients or []) if r]
    if not recipients:
        logger.warning("No valid recipients for: %s", subject)
        return False

    sender = from_email or FROM_EMAIL
    plain = strip_tags(html_body)

    def _worker():
        import time
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                msg = EmailMultiAlternatives(subject, plain, sender, recipients,
                                              reply_to=[sender])
                msg.attach_alternative(html_body, "text/html")
                msg.send(fail_silently=False)
                logger.info("✉ Sent '%s' → %s", subject, recipients)
                return
            except Exception as exc:
                if attempt < max_attempts:
                    wait = attempt * 5
                    logger.warning("✉ Attempt %d/%d failed '%s' → %s: %s - retrying in %ds",
                                   attempt, max_attempts, subject, recipients, exc, wait)
                    time.sleep(wait)
                else:
                    logger.error("✉ FAILED '%s' → %s after %d attempts: %s",
                                 subject, recipients, max_attempts, exc)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return True


def _get_subcounty_officers(sub_county):
    """Return email list of subcounty sports officers for a given sub-county."""
    from accounts.models import User
    if not sub_county:
        return []
    return list(
        User.objects.filter(
            role='subcounty_sports_officer',
            sub_county=sub_county,
            is_active=True,
        ).values_list('email', flat=True)
    )


def _get_users_by_role(role):
    """Return email list for all active users with a given role."""
    from accounts.models import User
    return list(
        User.objects.filter(role=role, is_active=True)
        .values_list('email', flat=True)
    )


def _get_coordinators_for_discipline(discipline):
    """Return email list of coordinators assigned to a discipline."""
    from accounts.models import User
    if not discipline:
        return _get_users_by_role('coordinator')
    return list(
        User.objects.filter(
            role='coordinator',
            assigned_discipline=discipline,
            is_active=True,
        ).values_list('email', flat=True)
    ) or _get_users_by_role('coordinator')


# ══════════════════════════════════════════════════════════════════════════════
#  WHATSAPP NOTIFICATIONS  (Brevo WhatsApp API)
# ══════════════════════════════════════════════════════════════════════════════

def send_whatsapp(phone_number, template_id, params=None):
    """
    Send a WhatsApp template message via Brevo WhatsApp API.

    In local development (DEBUG=True and no BREVO_API_KEY set), the message is
    printed to the terminal instead of being sent, so you can see exactly what
    would be delivered without needing real credentials.

    Requirements (configure in .env / settings):
      BREVO_API_KEY           — existing Brevo API key
      BREVO_WHATSAPP_SENDER   — your WhatsApp Business sender number (e.g. +254XXXXXXXXX)
      BREVO_WHATSAPP_TEMPLATE_CREDENTIALS — template ID for credentials message

    The phone number must be in international format (+254XXXXXXXXX).
    Returns True if dispatched (delivery is async), False if skipped/failed.
    """
    import requests as _req

    api_key  = getattr(settings, 'BREVO_API_KEY', '')
    sender   = getattr(settings, 'BREVO_WHATSAPP_SENDER', '')
    debug    = getattr(settings, 'DEBUG', False)

    if not phone_number or not phone_number.startswith('+'):
        logger.warning("WhatsApp skipped — invalid/missing phone: %r", phone_number)
        return False

    # ── Local dev: print to terminal instead of hitting Brevo API ────────────
    if debug and (not api_key or not sender):
        _print_whatsapp_to_terminal(phone_number, template_id, params)
        return True

    if not api_key or not sender:
        logger.warning(
            "WhatsApp not configured (missing BREVO_API_KEY or BREVO_WHATSAPP_SENDER). "
            "Skipping WhatsApp notification."
        )
        return False

    payload = {
        "senderNumber": sender,
        "contactNumbers": [phone_number],
        "templateId": template_id,
    }
    if params:
        payload["params"] = params

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": api_key,
    }

    def _worker():
        try:
            resp = _req.post(
                "https://api.brevo.com/v3/whatsapp/sendMessage",
                json=payload,
                headers=headers,
                timeout=15,
            )
            if resp.status_code in (200, 201, 202):
                logger.info("📱 WhatsApp sent template=%s → %s", template_id, phone_number)
            else:
                logger.error(
                    "📱 WhatsApp API error %d template=%s → %s: %s",
                    resp.status_code, template_id, phone_number, resp.text,
                )
        except Exception as exc:
            logger.error("📱 WhatsApp send failed template=%s → %s: %s", template_id, phone_number, exc)

    import threading
    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return True


def _print_whatsapp_to_terminal(phone_number, template_id, params=None):
    """Print a WhatsApp message to the terminal for local development inspection."""
    import threading
    # Resolve template body from known templates
    body_lines = []
    if params:
        # Credentials template (BREVO_WHATSAPP_TEMPLATE_CREDENTIALS)
        if "1" in params and "2" in params and "3" in params:
            body_lines = [
                f"Hello {params.get('1', '')}!",
                f"Your MKJ SUPA CUP portal account is ready.",
                f"Email:    {params.get('2', '')}",
                f"Password: {params.get('3', '')}",
                f"Role:     {params.get('5', '')}",
                f"Login:    {params.get('4', '')}",
                f"Please change your password on first login.",
            ]
        else:
            body_lines = [f"  param[{k}] = {v}" for k, v in params.items()]

    sep = "─" * 60
    lines = [
        "",
        sep,
        "📱  WHATSAPP MESSAGE (local dev — not actually sent)",
        sep,
        f"  To:          {phone_number}",
        f"  Template ID: {template_id}",
        "",
        "  Message body:",
        *[f"    {line}" for line in body_lines],
        sep,
        "",
    ]
    print("\n".join(lines), flush=True)
    logger.info("📱 WhatsApp (dev) template=%s → %s", template_id, phone_number)


def notify_credentials_whatsapp(phone_number, first_name, email, temp_password, role_label="Team Manager"):
    """
    Send login credentials to the user's WhatsApp number.
    Uses the BREVO_WHATSAPP_TEMPLATE_CREDENTIALS template.

    The template should be created in Brevo with variables:
      {{1}} = first name
      {{2}} = email
      {{3}} = password
      {{4}} = login URL
      {{5}} = role label

    Example template body:
      Hello {{1}}! Your MKJ SUPA CUP portal account is ready.
      Email: {{2}}
      Password: {{3}}
      Role: {{5}}
      Login: {{4}}
      Please change your password on first login.
    """
    template_id = getattr(settings, 'BREVO_WHATSAPP_TEMPLATE_CREDENTIALS', None)
    if not template_id:
        logger.warning(
            "BREVO_WHATSAPP_TEMPLATE_CREDENTIALS not set — skipping WhatsApp credentials message."
        )
        return False

    return send_whatsapp(
        phone_number=phone_number,
        template_id=int(template_id),
        params={
            "1": first_name,
            "2": email,
            "3": temp_password,
            "4": f"{SITE_URL}/portal/login/",
            "5": role_label,
        },
    )


def _base_html(title, body_content):
    """Wrap body content in a branded HTML email template."""
    logo_base = f"{SITE_URL}/static/img"
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f0f2f5; margin: 0; padding: 0; }}
.wrap {{ max-width: 600px; margin: 0 auto; background: #fff; border-radius: 12px; overflow: hidden;
         box-shadow: 0 4px 24px rgba(0,0,0,.08); }}
.logo-bar {{ background: #fff; padding: 20px 32px; text-align: center; border-bottom: 1px solid #e8edf5; }}
.logo-bar img {{ height: 56px; margin: 0 12px; vertical-align: middle; }}
.header {{ background: linear-gradient(135deg, #003388 0%, #124491 50%, #1a5db8 100%);
           padding: 28px 32px; text-align: center; }}
.header h1 {{ color: #fff; margin: 0; font-size: 16px; letter-spacing: 0.5px; font-weight: 600; line-height: 1.5; }}
.header p {{ color: rgba(255,255,255,.75); margin: 8px 0 0; font-size: 12px; letter-spacing: 0.3px; }}
.body {{ padding: 32px; color: #333; line-height: 1.7; font-size: 14px; }}
.body h2 {{ color: #124491; margin: 0 0 20px; font-size: 18px; font-weight: 700; }}
.info-box {{ background: linear-gradient(135deg, #e8edf5 0%, #f0f4ff 100%); border-left: 4px solid #124491;
             padding: 18px 20px; margin: 20px 0; border-radius: 6px; }}
.info-box dt {{ font-weight: 700; color: #003388; margin-top: 10px; font-size: 12px; text-transform: uppercase;
                letter-spacing: 0.5px; }}
.info-box dt:first-child {{ margin-top: 0; }}
.info-box dd {{ margin: 4px 0 0 0; color: #333; font-size: 14px; }}
.btn {{ display: inline-block; background: linear-gradient(135deg, #124491, #1a5db8); color: #fff !important;
        padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600;
        margin-top: 20px; font-size: 14px; letter-spacing: 0.3px; }}
.footer {{ background: #f8f9fb; padding: 24px 32px; text-align: center; font-size: 11px; color: #888;
           border-top: 1px solid #e8edf5; }}
.footer p {{ margin: 4px 0; }}
.footer .sign-off {{ font-weight: 600; color: #124491; font-size: 12px; margin-bottom: 8px; }}
.alert {{ background: #fff3e0; border-left: 4px solid #fcb900; padding: 14px 18px; margin: 20px 0;
          border-radius: 6px; color: #856404; font-size: 13px; }}
.divider {{ height: 1px; background: #e8edf5; margin: 24px 0; }}
</style></head><body>
<div style="padding:20px 0;">
<div class="wrap">
 <div class="logo-bar">
  <img src="{logo_base}/makueni_logo.png" alt="Makueni County" style="height:56px;">
  <img src="{logo_base}/TINA.jpeg" alt="Tina" style="height:56px;">
 </div>
 <div class="header">
  <h1>Welcome to Mutula Kilonzo Junior Supa Cup<br>Competition Management System</h1>
  <p>Makueni County Sports Department</p>
 </div>
 <div class="body">
  <h2>{title}</h2>
  {body_content}
 </div>
 <div class="footer">
  <p class="sign-off">MKJ SUPA CUP Administration</p>
  <p style="font-size:12px;color:#555;margin:6px 0;">&#128222; 0700 000 000 &nbsp;|&nbsp; Reply to: <a href="mailto:info@mkjsupacup.com" style="color:#124491;text-decoration:none;">info@mkjsupacup.com</a></p>
  <p>&copy; 2026 MKJ SUPA CUP - Makueni County Sports Department</p>
  <p><a href="{SITE_URL}" style="color:#124491;text-decoration:none;">{SITE_URL}</a></p>
 </div>
</div>
</div>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
#  1. ACCOUNT CREATED - Welcome + credentials
# ══════════════════════════════════════════════════════════════════════════════

def notify_account_created(user, temporary_password, role_label=None):
    """Send welcome email with login credentials to newly created user.
    Also sends credentials via WhatsApp if the user has a phone number configured."""
    role_display = role_label or dict(
        getattr(user, 'UserRole', {})
    ).get(user.role, user.role or 'User')

    body = f"""
<p>Dear <strong>{user.first_name} {user.last_name}</strong>,</p>
<p>Your MKJ SUPA CUP portal account has been created. You can now access
   the Competition Management System.</p>
<dl class="info-box">
 <dt>Login Email</dt><dd>{user.email}</dd>
 <dt>Temporary Password</dt><dd><code>{temporary_password}</code></dd>
 <dt>Role</dt><dd>{role_display}</dd>
</dl>
<div class="alert">⚠️ You will be required to change your password on first login.</div>
<a href="{SITE_URL}/portal/login/" class="btn">Login to Portal</a>
<p style="margin-top:24px;font-size:13px;color:#666">
  If you did not request this account, please ignore this email.</p>"""

    _send(
        f"Welcome to MKJ SUPA CUP - {role_display}",
        _base_html("Your Account Details", body),
        [user.email],
    )

    # WhatsApp credentials (covers both email + WA from one call)
    phone = getattr(user, 'phone', None)
    if phone:
        notify_wa_credentials(
            phone=phone,
            first_name=user.first_name,
            email=user.email,
            temp_password=temporary_password,
            role_label=role_display,
        )


# ══════════════════════════════════════════════════════════════════════════════
#  2. NEW PLAYER REGISTERED
# ══════════════════════════════════════════════════════════════════════════════

def notify_new_player(player, team=None):
    """Notify subcounty officers and verification officers about a new player."""
    team = team or getattr(player, 'team', None)
    team_name = team.name if team else 'Unknown Team'
    sub_county = getattr(team, 'sub_county', '') if team else getattr(player, 'sub_county', '')
    player_name = f"{player.first_name} {player.last_name}"

    body = f"""
<p>A new player has been registered and requires attention.</p>
<dl class="info-box">
 <dt>Player</dt><dd>{player_name}</dd>
 <dt>Team</dt><dd>{team_name}</dd>
 <dt>Sub-County</dt><dd>{sub_county or 'N/A'}</dd>
 <dt>Position</dt><dd>{getattr(player, 'get_position_display', lambda: player.position)()}</dd>
</dl>
<p>Please review the player's documents and verification status in the portal.</p>
<a href="{SITE_URL}/portal/dashboard/" class="btn">Review in Portal</a>"""

    recipients = _get_subcounty_officers(sub_county)
    recipients += _get_users_by_role('verification_officer')
    # Deduplicate
    recipients = list(set(recipients))

    _send(
        f"New Player Registered - {player_name} ({team_name})",
        _base_html("New Player Registration", body),
        recipients,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  3. FIXTURE CREATED / UPDATED
# ══════════════════════════════════════════════════════════════════════════════

def _get_ward_team_managers_for_team(team):
    """Return email list of ward-level team managers for a given Team.

    For ward-level teams, finds the manager via the team's source_discipline
    (CountyDiscipline at level='ward'), looking up the User with
    role='team_manager' whose ward and sub_county match.
    Also includes team.manager directly if set.
    Requirement: 13.4
    """
    from accounts.models import User
    if not team:
        return []
    emails = []
    # Always include the direct team.manager FK if present
    if team.manager and team.manager.email:
        emails.append(team.manager.email)
    # For ward-level teams, also look up via ward + sub_county on User
    try:
        discipline = team.source_discipline
        if discipline and discipline.level == 'ward' and discipline.ward and discipline.sub_county:
            ward_managers = User.objects.filter(
                role='team_manager',
                ward=discipline.ward,
                sub_county=discipline.sub_county,
                is_active=True,
            ).values_list('email', flat=True)
            emails.extend(list(ward_managers))
    except Exception:
        pass
    return emails


def notify_fixture_update(fixture, action='updated'):
    """Notify team managers (including ward-level) and subcounty officers about fixture changes.

    Req 13.4: Ward Team Managers of both participating teams are emailed with
    venue, date, and kick-off time when a fixture is created/published.
    """
    home = fixture.home_team
    away = fixture.away_team
    match_label = f"{home.name if home else 'TBD'} vs {away.name if away else 'TBD'}"
    venue_name = str(fixture.venue) if fixture.venue else 'TBD'
    match_date = fixture.match_date.strftime('%d %b %Y') if fixture.match_date else 'TBD'
    kickoff = fixture.kickoff_time.strftime('%H:%M') if fixture.kickoff_time else 'TBD'
    status = fixture.get_status_display() if hasattr(fixture, 'get_status_display') else fixture.status

    body = f"""
<p>A fixture has been <strong>{action}</strong>.</p>
<dl class="info-box">
 <dt>Match</dt><dd>{match_label}</dd>
 <dt>Date</dt><dd>{match_date}</dd>
 <dt>Kick-off</dt><dd>{kickoff}</dd>
 <dt>Venue</dt><dd>{venue_name}</dd>
 <dt>Status</dt><dd>{status}</dd>
 <dt>Competition</dt><dd>{fixture.competition.name if fixture.competition else 'N/A'}</dd>
</dl>
<a href="{SITE_URL}/portal/dashboard/" class="btn">View in Portal</a>"""

    recipients = []
    # Team managers — includes ward-level TMs (Req 13.4)
    recipients += _get_ward_team_managers_for_team(home)
    recipients += _get_ward_team_managers_for_team(away)
    # Subcounty officers for both teams
    if home:
        recipients += _get_subcounty_officers(getattr(home, 'sub_county', ''))
    if away:
        recipients += _get_subcounty_officers(getattr(away, 'sub_county', ''))

    recipients = list(set(recipients))

    _send(
        f"Fixture {action.title()} - {match_label}",
        _base_html(f"Fixture {action.title()}", body),
        recipients,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  3b. PLAYER VERIFICATION STATUS CHANGE → Ward Team Manager  (Req 13.5)
# ══════════════════════════════════════════════════════════════════════════════

def notify_ward_tm_verification_status(player, status, rejection_reason=''):
    """Email the Ward Team Manager when a player's verification status changes.

    Args:
        player: CountyPlayer instance whose verification status changed.
        status: 'verified' or 'rejected'.
        rejection_reason: Human-readable reason string (required when rejected).

    Requirement: 13.5
    Returns True if the email was dispatched (delivery is async), False otherwise.
    """
    from accounts.models import User

    player_name = f"{player.first_name} {player.last_name}"

    # Locate the Ward Team Manager: match by ward and sub_county on User
    ward = getattr(player, 'ward', '') or (
        player.discipline.ward if player.discipline else ''
    )
    sub_county = getattr(player, 'sub_county', '') or (
        player.discipline.sub_county if player.discipline else ''
    )

    ward_tm_email = None
    if ward and sub_county:
        tm = User.objects.filter(
            role='team_manager',
            ward=ward,
            sub_county=sub_county,
            is_active=True,
        ).first()
        if tm and tm.email:
            ward_tm_email = tm.email

    if not ward_tm_email:
        logger.warning(
            "notify_ward_tm_verification_status: no ward TM found for "
            "player %s (ward=%r, sub_county=%r)", player_name, ward, sub_county,
        )
        return False

    if status == 'verified':
        outcome_label = 'Approved ✅'
        outcome_detail = (
            '<p>The player has passed all verification steps and is eligible '
            'for sub-county squad selection.</p>'
        )
        subject_suffix = 'Approved'
    else:
        reason_text = rejection_reason or 'No reason provided'
        outcome_label = f'Rejected ❌'
        outcome_detail = (
            f'<p>The player did not pass verification. Reason:</p>'
            f'<div class="alert">{reason_text}</div>'
        )
        subject_suffix = 'Rejected'

    body = f"""
<p>Dear Ward Team Manager,</p>
<p>The verification status for player <strong>{player_name}</strong> has been updated.</p>
<dl class="info-box">
 <dt>Player</dt><dd>{player_name}</dd>
 <dt>Outcome</dt><dd>{outcome_label}</dd>
</dl>
{outcome_detail}
<p>Please log in to the portal for full details.</p>
<a href="{SITE_URL}/portal/dashboard/" class="btn">View in Portal</a>"""

    return _send(
        f"Player Verification {subject_suffix} - {player_name}",
        _base_html(f"Player Verification {subject_suffix}", body),
        [ward_tm_email],
    )


# ══════════════════════════════════════════════════════════════════════════════
#  4. PLAYER VERIFICATION NEEDED
# ══════════════════════════════════════════════════════════════════════════════

def notify_verification_needed(player, team=None):
    """Notify verification officers that a player needs document review."""
    team = team or getattr(player, 'team', None)
    player_name = f"{player.first_name} {player.last_name}"
    team_name = team.name if team else 'Unknown Team'

    body = f"""
<p>A player requires document verification.</p>
<dl class="info-box">
 <dt>Player</dt><dd>{player_name}</dd>
 <dt>Team</dt><dd>{team_name}</dd>
 <dt>Documents Uploaded</dt><dd>{'Yes' if getattr(player, 'documents_uploaded', False) else 'Pending'}</dd>
</dl>
<p>Please log in to the portal to review and verify the player's documents.</p>
<a href="{SITE_URL}/portal/dashboard/" class="btn">Verify Player</a>"""

    recipients = _get_users_by_role('verification_officer')
    _send(
        f"Verification Required - {player_name}",
        _base_html("Player Verification Required", body),
        recipients,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  5. SQUAD SUBMITTED
# ══════════════════════════════════════════════════════════════════════════════

def notify_squad_submitted(submission):
    """Notify coordinator when a team submits their match squad."""
    fixture = submission.fixture
    team = submission.team
    match_label = f"{fixture.home_team.name if fixture.home_team else 'TBD'} vs {fixture.away_team.name if fixture.away_team else 'TBD'}"

    body = f"""
<p><strong>{team.name}</strong> has submitted their squad for an upcoming match.</p>
<dl class="info-box">
 <dt>Match</dt><dd>{match_label}</dd>
 <dt>Team</dt><dd>{team.name}</dd>
 <dt>Players</dt><dd>{submission.squad_players.count() if hasattr(submission, 'squad_players') else 'N/A'}</dd>
</dl>
<a href="{SITE_URL}/portal/dashboard/" class="btn">Review Squad</a>"""

    discipline = getattr(fixture.competition, 'sport_type', '') if fixture.competition else ''
    recipients = _get_coordinators_for_discipline(discipline)

    _send(
        f"Squad Submitted - {team.name} for {match_label}",
        _base_html("Squad Submission", body),
        recipients,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  6. MATCH REPORT SUBMITTED
# ══════════════════════════════════════════════════════════════════════════════

def notify_match_report_submitted(match_report):
    """Notify coordinator when referee submits a match report."""
    fixture = match_report.fixture
    match_label = f"{fixture.home_team.name if fixture.home_team else 'TBD'} vs {fixture.away_team.name if fixture.away_team else 'TBD'}"

    body = f"""
<p>A match report has been submitted and needs review.</p>
<dl class="info-box">
 <dt>Match</dt><dd>{match_label}</dd>
 <dt>Score</dt><dd>{match_report.home_score} - {match_report.away_score}</dd>
 <dt>Referee</dt><dd>{match_report.referee.user.get_full_name() if match_report.referee and match_report.referee.user else 'N/A'}</dd>
 <dt>Status</dt><dd>{match_report.get_status_display()}</dd>
</dl>
<a href="{SITE_URL}/portal/dashboard/" class="btn">Review Report</a>"""

    discipline = getattr(fixture.competition, 'sport_type', '') if fixture.competition else ''
    recipients = _get_coordinators_for_discipline(discipline)

    _send(
        f"Match Report Submitted - {match_label}",
        _base_html("Match Report for Review", body),
        recipients,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  7. TEAM REGISTERED / STATUS CHANGED
# ══════════════════════════════════════════════════════════════════════════════

def notify_team_status(team, action='registered'):
    """Notify admins and subcounty officers about team registration/status changes."""
    body = f"""
<p>A team has been <strong>{action}</strong>.</p>
<dl class="info-box">
 <dt>Team</dt><dd>{team.name}</dd>
 <dt>Sub-County</dt><dd>{team.sub_county or 'N/A'}</dd>
 <dt>Manager</dt><dd>{team.manager.get_full_name() if team.manager else 'N/A'}</dd>
 <dt>Status</dt><dd>{team.get_status_display() if hasattr(team, 'get_status_display') else team.status}</dd>
</dl>
<a href="{SITE_URL}/portal/dashboard/" class="btn">View in Portal</a>"""

    recipients = _get_subcounty_officers(team.sub_county)
    recipients += _get_users_by_role('admin')
    recipients = list(set(recipients))

    _send(
        f"Team {action.title()} - {team.name}",
        _base_html(f"Team {action.title()}", body),
        recipients,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  8. PASSWORD RESET
# ══════════════════════════════════════════════════════════════════════════════

def notify_password_reset(user, new_password):
    """Send password reset email + WhatsApp with new credentials."""
    body = f"""
<p>Dear <strong>{user.first_name} {user.last_name}</strong>,</p>
<p>Your password has been reset by an administrator.</p>
<dl class="info-box">
 <dt>Login Email</dt><dd>{user.email}</dd>
 <dt>New Password</dt><dd><code>{new_password}</code></dd>
</dl>
<div class="alert">⚠️ Please change your password immediately after login.</div>
<a href="{SITE_URL}/portal/login/" class="btn">Login Now</a>"""

    _send(
        "Password Reset - MKJ SUPA CUP",
        _base_html("Password Reset", body),
        [user.email],
    )

    # WhatsApp notification
    phone = getattr(user, 'phone', None)
    if phone:
        notify_wa_password_reset(phone, user.first_name, new_password)


# ══════════════════════════════════════════════════════════════════════════════
#  9. GENERIC ACTION-NEEDED NOTIFICATION
# ══════════════════════════════════════════════════════════════════════════════

def notify_action_needed(recipients, title, message, action_url=None):
    """Send a generic notification when a user's attention is needed."""
    action_btn = ''
    if action_url:
        action_btn = f'<a href="{action_url}" class="btn">Take Action</a>'

    body = f"""
<p>{message}</p>
{action_btn}"""

    _send(
        f"Action Required - {title}",
        _base_html(title, body),
        recipients if isinstance(recipients, list) else [recipients],
    )


# ══════════════════════════════════════════════════════════════════════════════
#  WHATSAPP NOTIFICATION FUNCTIONS  (Brevo template-based)
#
#  Each function maps to a Brevo WhatsApp template.
#  Template variables {{1}}, {{2}} ... are passed as params dict.
#
#  TEMPLATE SETUP IN BREVO (WhatsApp → Templates):
#  ─────────────────────────────────────────────────
#  1. CREDENTIALS (BREVO_WHATSAPP_TEMPLATE_CREDENTIALS)
#     "Hello {{1}}! Your MKJ SUPA CUP account is ready.\nEmail: {{2}}\nPassword: {{3}}\nRole: {{4}}\nLogin: {{5}}\nChange password on first login."
#
#  2. PASSWORD_RESET (BREVO_WHATSAPP_TEMPLATE_PASSWORD_RESET)
#     "Hello {{1}}! Your MKJ SUPA CUP password has been reset.\nNew password: {{2}}\nLogin: {{3}}\nChange it immediately after login."
#
#  3. DEADLINE (BREVO_WHATSAPP_TEMPLATE_DEADLINE)
#     "⏰ MKJ SUPA CUP Reminder — {{1}}.\nDeadline: {{2}}.\n{{3}}"
#
#  4. TRANSFER (BREVO_WHATSAPP_TEMPLATE_TRANSFER)
#     "🔄 Transfer Update — {{1}} {{2}}.\nStatus: {{3}}\nFrom: {{4}} → To: {{5}}\n{{6}}"
#
#  5. LONGLIST_STATUS (BREVO_WHATSAPP_TEMPLATE_LONGLIST_STATUS)
#     "📋 Longlist Update — {{1}} Ward ({{2}}).\nStatus: {{3}}\n{{4}}"
#
#  6. SQUAD_RESULT (BREVO_WHATSAPP_TEMPLATE_SQUAD_RESULT)
#     "⚽ Match Result — {{1}} vs {{2}}.\nScore: {{3}} – {{4}}\n{{5}}"
# ══════════════════════════════════════════════════════════════════════════════

def _get_template_id(setting_name):
    """Return template ID integer from settings, or None if not configured."""
    val = getattr(settings, setting_name, '')
    if not val:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _wa(phone, setting_name, params, label='notification'):
    """
    Generic WhatsApp send helper.
    Resolves template ID from settings, calls send_whatsapp on a background thread.
    Returns True if dispatched, False if skipped.
    """
    template_id = _get_template_id(setting_name)
    if not template_id:
        logger.info('WhatsApp %s skipped — %s not set in settings.', label, setting_name)
        return False
    return send_whatsapp(phone_number=phone, template_id=template_id, params=params)


# ── 1. Credentials (new account) ─────────────────────────────────────────────

def notify_wa_credentials(phone, first_name, email, temp_password, role_label):
    """
    Send new account credentials via WhatsApp.
    Template variables: {{1}}=first_name {{2}}=email {{3}}=password {{4}}=role {{5}}=login_url
    """
    return _wa(phone, 'BREVO_WHATSAPP_TEMPLATE_CREDENTIALS', {
        '1': first_name,
        '2': email,
        '3': temp_password,
        '4': role_label,
        '5': f"{SITE_URL}/portal/login/",
    }, label='credentials')


# ── 2. Password reset ────────────────────────────────────────────────────────

def notify_wa_password_reset(phone, first_name, new_password):
    """
    Send password reset notification via WhatsApp.
    Template variables: {{1}}=first_name {{2}}=new_password {{3}}=login_url
    """
    return _wa(phone, 'BREVO_WHATSAPP_TEMPLATE_PASSWORD_RESET', {
        '1': first_name,
        '2': new_password,
        '3': f"{SITE_URL}/portal/login/",
    }, label='password_reset')


# ── 3. Deadline reminder ─────────────────────────────────────────────────────

def notify_wa_deadline(phone, event_label, deadline_str, action_text=''):
    """
    Send a deadline reminder via WhatsApp.
    Template variables: {{1}}=event {{2}}=deadline {{3}}=action_text
    Examples:
        notify_wa_deadline(phone, 'Longlist Submission', '15 Jul 2026 at 17:00', 'Submit your longlist before the deadline.')
        notify_wa_deadline(phone, 'Squad Selection', '16 Jul 2026 at 10:00', 'Select your match-day squad.')
    """
    return _wa(phone, 'BREVO_WHATSAPP_TEMPLATE_DEADLINE', {
        '1': event_label,
        '2': deadline_str,
        '3': action_text or f"Visit {SITE_URL}/portal/login/ to action.",
    }, label='deadline')


# ── 4. Transfer status update ────────────────────────────────────────────────

def notify_wa_transfer_update(phone, first_name, last_name, status_label,
                               from_ward, to_ward, notes=''):
    """
    Notify Ward TM of a transfer decision via WhatsApp.
    Template variables: {{1}}=first_name {{2}}=last_name {{3}}=status {{4}}=from_ward {{5}}=to_ward {{6}}=notes
    """
    return _wa(phone, 'BREVO_WHATSAPP_TEMPLATE_TRANSFER', {
        '1': first_name,
        '2': last_name,
        '3': status_label,
        '4': from_ward,
        '5': to_ward,
        '6': notes or 'No additional notes.',
    }, label='transfer_update')


# ── 5. Longlist status update ────────────────────────────────────────────────

def notify_wa_longlist_status(phone, ward, sport_label, status_label, message=''):
    """
    Notify Ward TM of their longlist status change via WhatsApp.
    Template variables: {{1}}=ward {{2}}=sport {{3}}=status {{4}}=message
    Examples: approved, returned for corrections, etc.
    """
    return _wa(phone, 'BREVO_WHATSAPP_TEMPLATE_LONGLIST_STATUS', {
        '1': ward,
        '2': sport_label,
        '3': status_label,
        '4': message or f"Log in at {SITE_URL}/ligi/longlist/ to view.",
    }, label='longlist_status')


# ── 6. Match result / squad outcome ─────────────────────────────────────────

def notify_wa_match_result(phone, home_team, away_team, home_score, away_score, note=''):
    """
    Send match result via WhatsApp to team manager.
    Template variables: {{1}}=home_team {{2}}=away_team {{3}}=home_score {{4}}=away_score {{5}}=note
    """
    return _wa(phone, 'BREVO_WHATSAPP_TEMPLATE_SQUAD_RESULT', {
        '1': home_team,
        '2': away_team,
        '3': str(home_score),
        '4': str(away_score),
        '5': note or 'Match completed.',
    }, label='match_result')


# ── Bulk deadline broadcast ───────────────────────────────────────────────────

def broadcast_wa_deadline(role_or_phones, event_label, deadline_str, action_text=''):
    """
    Send deadline reminder to all users with a given role (or a list of phone numbers).
    
    Usage:
        broadcast_wa_deadline('team_manager', 'Squad Submission', '16 Jul 2026 17:00')
        broadcast_wa_deadline(['+254712345678', '+254723456789'], 'Longlist Deadline', '15 Jul 2026')
    """
    from accounts.models import User

    if isinstance(role_or_phones, str):
        # It's a role — get all phones for that role
        phones = list(
            User.objects.filter(role=role_or_phones, is_active=True, phone__isnull=False)
            .exclude(phone='')
            .values_list('phone', flat=True)
        )
    else:
        phones = role_or_phones

    sent = 0
    for phone in phones:
        if notify_wa_deadline(phone, event_label, deadline_str, action_text):
            sent += 1

    logger.info('📱 Deadline broadcast "%s" → sent to %d/%d recipients', event_label, sent, len(phones))
    return sent
