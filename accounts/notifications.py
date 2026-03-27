"""
MKJ SUPA CUP - Centralized Email Notification System

Sends HTML emails for:
  1. Account creation (welcome + credentials)
  2. New player registered → subcounty officer, verification officer
  3. Fixture created/updated → team managers, subcounty officers
  4. Player verification needed → verification officer
  5. Squad submitted → coordinator
  6. Match report submitted → coordinator
  7. Team registration → admin, subcounty officer

All emails are dispatched on a background daemon thread so they never
block the web request - timeouts / SMTP errors only appear in server logs.
"""
import logging
import threading
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

SITE_URL = getattr(settings, 'SITE_URL', 'https://mkjsupacup.com')
FROM_EMAIL = getattr(settings, 'DEFAULT_FROM_EMAIL', 'MKJ SUPA CUP <info@mkjsupacup.com>')


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _send(subject, html_body, recipients, fail_silently=True):
    """
    Send an HTML email on a background daemon thread.
    Returns immediately - never blocks the web request.
    Filters out blank addresses.  Retries up to 3 times on transient errors.
    """
    recipients = [r for r in (recipients or []) if r]
    if not recipients:
        logger.warning("No valid recipients for: %s", subject)
        return False

    plain = strip_tags(html_body)

    def _worker():
        import time
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                msg = EmailMultiAlternatives(subject, plain, FROM_EMAIL, recipients)
                msg.attach_alternative(html_body, "text/html")
                msg.send(fail_silently=False)
                logger.info("✉ Sent '%s' → %s", subject, recipients)
                return
            except Exception as exc:
                if attempt < max_attempts:
                    wait = attempt * 5  # 5s, 10s
                    logger.warning("✉ Attempt %d/%d failed '%s' → %s: %s - retrying in %ds",
                                   attempt, max_attempts, subject, recipients, exc, wait)
                    time.sleep(wait)
                else:
                    logger.error("✉ FAILED '%s' → %s after %d attempts: %s",
                                 subject, recipients, max_attempts, exc)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return True  # fired - delivery result logged asynchronously


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


def _base_html(title, body_content):
    """Wrap body content in a branded HTML email template."""
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f4f6f8; margin: 0; padding: 0; }}
.wrap {{ max-width: 600px; margin: 0 auto; background: #fff; }}
.header {{ background: linear-gradient(135deg, #003388, #124491); padding: 24px 32px; text-align: center; }}
.header h1 {{ color: #fff; margin: 0; font-size: 20px; letter-spacing: 1px; }}
.header p {{ color: rgba(255,255,255,.7); margin: 4px 0 0; font-size: 12px; }}
.body {{ padding: 32px; color: #333; line-height: 1.6; font-size: 14px; }}
.body h2 {{ color: #124491; margin: 0 0 16px; font-size: 18px; }}
.info-box {{ background: #e8edf5; border-left: 4px solid #124491; padding: 16px; margin: 16px 0; border-radius: 4px; }}
.info-box dt {{ font-weight: 700; color: #003388; margin-top: 8px; }}
.info-box dt:first-child {{ margin-top: 0; }}
.info-box dd {{ margin: 2px 0 0 0; color: #333; }}
.btn {{ display: inline-block; background: #124491; color: #fff; padding: 12px 28px; border-radius: 6px;
        text-decoration: none; font-weight: 600; margin-top: 16px; }}
.footer {{ background: #f4f6f8; padding: 16px 32px; text-align: center; font-size: 11px; color: #999; }}
.alert {{ background: #fff3e0; border-left: 4px solid #fcb900; padding: 12px 16px; margin: 16px 0; border-radius: 4px; color: #856404; }}
</style></head><body>
<div class="wrap">
 <div class="header">
  <h1>MKJ SUPA CUP</h1>
  <p>Governor Mutula Kilonzo Junior Super Cup - Makueni County</p>
 </div>
 <div class="body">
  <h2>{title}</h2>
  {body_content}
 </div>
 <div class="footer">
  &copy; 2026 MKJ SUPA CUP - Makueni County Sports Department<br>
  <a href="{SITE_URL}" style="color:#124491">{SITE_URL}</a>
 </div>
</div>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
#  1. ACCOUNT CREATED - Welcome + credentials
# ══════════════════════════════════════════════════════════════════════════════

def notify_account_created(user, temporary_password, role_label=None):
    """Send welcome email with login credentials to newly created user."""
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
        _base_html("Welcome to the Portal", body),
        [user.email],
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

def notify_fixture_update(fixture, action='updated'):
    """Notify team managers and subcounty officers about fixture changes."""
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
    # Team managers
    if home and home.manager and home.manager.email:
        recipients.append(home.manager.email)
    if away and away.manager and away.manager.email:
        recipients.append(away.manager.email)
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
    """Send password reset email with new credentials."""
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
