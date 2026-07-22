"""
teams/subcounty_finals.py

Business logic for the MKJ Supa Cup Subcounty Finals pipeline.

Handles:
  - Age eligibility checks (strict Under-23, ages 18-23 inclusive)
  - Ward All Stars squad age validation
  - Outside-Ligi player request flow (submit → director → CSO)
  - Promoting a Ligi Mashinani ward player to the allstars longlist
"""
import logging
from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

# Age bracket constants
SUBCOUNTY_FINALS_MIN_AGE = 18
SUBCOUNTY_FINALS_MAX_AGE = 23


# ── Age eligibility ────────────────────────────────────────────────────────

def check_subcounty_finals_age_eligibility(
    date_of_birth,
    competition_start_date,
):
    """
    Return (True, "") if 18 <= age_on_competition_day <= 23.
    Return (False, reason_str) otherwise.

    Age is calculated on competition_start_date (not today).
    """
    if date_of_birth is None:
        return False, "Date of birth is required for Subcounty Finals."

    ref = competition_start_date
    age = (
        ref.year - date_of_birth.year
        - ((ref.month, ref.day) < (date_of_birth.month, date_of_birth.day))
    )

    if age < SUBCOUNTY_FINALS_MIN_AGE:
        return False, (
            f"Player is {age} years old — minimum age is "
            f"{SUBCOUNTY_FINALS_MIN_AGE} for Subcounty Finals."
        )
    if age > SUBCOUNTY_FINALS_MAX_AGE:
        return False, (
            f"Player is {age} years old — maximum age is "
            f"{SUBCOUNTY_FINALS_MAX_AGE} for Subcounty Finals (Under-23)."
        )
    return True, ""


def validate_ward_allstars_squad_age(squad_players, competition):
    """
    Validate all squad_players are age-eligible (18-23) for the competition.
    Raises ValidationError listing all ineligible players if any fail.
    """
    ref_date = getattr(competition, 'start_date', None) or timezone.now().date()
    errors = []
    for player in squad_players:
        eligible, reason = check_subcounty_finals_age_eligibility(
            player.date_of_birth, ref_date
        )
        if not eligible:
            errors.append(f"{player.first_name} {player.last_name}: {reason}")

    if errors:
        raise ValidationError(
            "The following players do not meet the Under-23 age requirement:\n"
            + "\n".join(errors)
        )


# ── Promote ward player to allstars longlist ───────────────────────────────

@transaction.atomic
def promote_ligi_player_to_allstars(county_player, allstars_team):
    """
    Copy a Ligi Mashinani CountyPlayer (ward level) into the allstars team's
    subcounty discipline.

    - Validates age eligibility.
    - Creates a new CountyPlayer at level=subcounty linked to allstars_team.
    - Sets source_ward_player to the original ward player.
    - Returns the new CountyPlayer.

    Raises ValidationError if:
      - Player is not age-eligible.
      - Player is already in this allstars team.
    """
    from teams.models import CountyPlayer

    competition = allstars_team.competition
    ref_date = getattr(competition, 'start_date', None) or timezone.now().date()

    eligible, reason = check_subcounty_finals_age_eligibility(
        county_player.date_of_birth, ref_date
    )
    if not eligible:
        raise ValidationError(f"Cannot add {county_player}: {reason}")

    # Check not already added
    if CountyPlayer.objects.filter(
        allstars_team=allstars_team,
        national_id_number=county_player.national_id_number,
    ).exists():
        raise ValidationError(
            f"{county_player.first_name} {county_player.last_name} "
            f"is already in this Ward All Stars team."
        )

    sc_discipline = allstars_team.subcounty_discipline
    if sc_discipline is None:
        raise ValidationError(
            "Ward All Stars team has no subcounty discipline assigned. "
            "Contact your Sub-County Sports Officer."
        )

    new_player = CountyPlayer.objects.create(
        discipline=sc_discipline,
        first_name=county_player.first_name,
        last_name=county_player.last_name,
        date_of_birth=county_player.date_of_birth,
        national_id_number=county_player.national_id_number,
        phone=county_player.phone,
        sub_county=county_player.sub_county,
        ward=county_player.ward,
        position=county_player.position,
        ligi_mashinani_team=county_player.ligi_mashinani_team,
        photo=county_player.photo,
        id_document=county_player.id_document,
        birth_certificate=county_player.birth_certificate,
        verification_status="pending",
        allstars_team=allstars_team,
        is_outside_ligi=False,
        source_ward_player=county_player,
    )

    logger.info(
        "Promoted ward player %s (ID: %s) to allstars team %s",
        new_player.get_full_name() if hasattr(new_player, 'get_full_name') else f"{new_player.first_name} {new_player.last_name}",
        new_player.national_id_number,
        allstars_team.official_name,
    )
    return new_player


# ── Outside-Ligi Player Request ────────────────────────────────────────────

def submit_outside_ligi_player_request(
    ward_allstars_team,
    player_name,
    national_id,
    date_of_birth,
    justification,
    requested_by_user,
    supporting_doc=None,
):
    """
    Submit a request to add a player not in Ligi Mashinani.

    Flow: TM submits → PENDING_DIRECTOR → Director reviews → forwards to CSO → CSO approves.

    Raises ValidationError if:
      - national_id already has a pending/approved request for this team
      - Player is not age-eligible
    Returns the created OutsideLigiPlayerRequest.
    """
    from teams.models import OutsideLigiPlayerRequest, OutsideLigiRequestStatus

    competition = ward_allstars_team.competition
    ref_date = getattr(competition, 'start_date', None) or timezone.now().date()

    eligible, reason = check_subcounty_finals_age_eligibility(date_of_birth, ref_date)
    if not eligible:
        raise ValidationError(reason)

    if OutsideLigiPlayerRequest.objects.filter(
        ward_allstars=ward_allstars_team,
        national_id=national_id,
    ).exclude(
        status__in=[
            OutsideLigiRequestStatus.CSO_REJECTED,
            OutsideLigiRequestStatus.DIRECTOR_REJECTED,
        ]
    ).exists():
        raise ValidationError(
            f"A player with national ID {national_id} already has an active "
            f"request for this ward all-stars team."
        )

    request_obj = OutsideLigiPlayerRequest.objects.create(
        ward_allstars=ward_allstars_team,
        player_name=player_name,
        national_id=national_id,
        date_of_birth=date_of_birth,
        justification=justification,
        supporting_doc=supporting_doc,
        status=OutsideLigiRequestStatus.PENDING_DIRECTOR,
        requested_by=requested_by_user,
    )

    # Notify Director of Sports
    _notify_director_outside_ligi(request_obj)
    logger.info(
        "Outside-Ligi player request submitted: %s for %s (by %s)",
        player_name, ward_allstars_team.official_name, requested_by_user.email,
    )
    return request_obj


@transaction.atomic
def director_review_outside_ligi_request(request_obj, director_user, action, notes=""):
    """
    Director of Sports reviews: approve (forward to CSO) or reject.
    """
    from teams.models import OutsideLigiRequestStatus

    if request_obj.status != OutsideLigiRequestStatus.PENDING_DIRECTOR:
        raise ValidationError("Request is no longer pending Director review.")

    request_obj.director_reviewed_by = director_user
    request_obj.director_reviewed_at = timezone.now()
    request_obj.director_notes = notes

    if action == "approve":
        request_obj.status = OutsideLigiRequestStatus.FORWARDED_CSO
        request_obj.save()
        _notify_cso_outside_ligi(request_obj)
    elif action == "reject":
        request_obj.status = OutsideLigiRequestStatus.DIRECTOR_REJECTED
        request_obj.save()
        _notify_tm_outside_ligi_decision(request_obj, approved=False)
    else:
        raise ValueError(f"Invalid action: {action}. Expected 'approve' or 'reject'.")


@transaction.atomic
def cso_final_review_outside_ligi_request(request_obj, cso_user, action, notes=""):
    """
    Chief Sports Officer: final approval creates the CountyPlayer record; rejection notifies TM.
    """
    from teams.models import OutsideLigiRequestStatus, CountyPlayer

    if request_obj.status != OutsideLigiRequestStatus.FORWARDED_CSO:
        raise ValidationError("Request must be forwarded by Director of Sports first.")

    request_obj.cso_reviewed_by = cso_user
    request_obj.cso_reviewed_at = timezone.now()
    request_obj.cso_notes = notes

    if action == "approve":
        request_obj.status = OutsideLigiRequestStatus.CSO_APPROVED
        request_obj.save()

        # Create CountyPlayer at subcounty level
        sc_discipline = request_obj.ward_allstars.subcounty_discipline
        if sc_discipline is None:
            raise ValidationError(
                "Ward All Stars team has no subcounty discipline. "
                "Ask the SCSO to set it up."
            )
        name_parts = request_obj.player_name.strip().split()
        first_name = name_parts[0] if name_parts else request_obj.player_name
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

        player = CountyPlayer.objects.create(
            discipline=sc_discipline,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=request_obj.date_of_birth,
            national_id_number=request_obj.national_id,
            phone="+254000000000",  # placeholder — TM must update
            sub_county=request_obj.ward_allstars.sub_county,
            ward=request_obj.ward_allstars.ward,
            verification_status="pending",
            allstars_team=request_obj.ward_allstars,
            is_outside_ligi=True,
            outside_ligi_request=request_obj,
        )
        _notify_tm_outside_ligi_decision(request_obj, approved=True, player=player)
        logger.info(
            "CSO approved outside-Ligi player %s for %s — CountyPlayer pk=%s created",
            request_obj.player_name, request_obj.ward_allstars.official_name, player.pk,
        )

    elif action == "reject":
        request_obj.status = OutsideLigiRequestStatus.CSO_REJECTED
        request_obj.save()
        _notify_tm_outside_ligi_decision(request_obj, approved=False)
    else:
        raise ValueError(f"Invalid action: {action}. Expected 'approve' or 'reject'.")


# ── Notification helpers ───────────────────────────────────────────────────

def _notify_director_outside_ligi(request_obj):
    """Email Director of Sports about a new outside-Ligi request."""
    try:
        from accounts.models import User, UserRole
        from accounts.notifications import _send, _base_html, SITE_URL

        directors = User.objects.filter(
            role=UserRole.DIRECTOR_SPORTS, is_active=True
        ).values_list('email', flat=True)
        if not directors:
            return

        body = f"""
<p>A new outside-Ligi player inclusion request has been submitted for your review.</p>
<dl class="info-box">
  <dt>Player</dt><dd>{request_obj.player_name} (ID: {request_obj.national_id})</dd>
  <dt>Ward All Stars Team</dt><dd>{request_obj.ward_allstars.official_name}</dd>
  <dt>Submitted by</dt><dd>{request_obj.requested_by.get_full_name() if request_obj.requested_by else 'Team Manager'}</dd>
  <dt>Justification</dt><dd>{request_obj.justification}</dd>
</dl>
<a href="{SITE_URL}/portal/director/outside-ligi-requests/{request_obj.pk}/" class="btn">Review Request</a>"""
        _send(
            f"Outside-Ligi Player Request — {request_obj.ward_allstars.official_name}",
            _base_html("Outside-Ligi Player Request", body),
            list(directors),
        )
    except Exception as exc:
        logger.warning("Failed to notify Director of outside-Ligi request: %s", exc)


def _notify_cso_outside_ligi(request_obj):
    """Email Chief Sports Officer after Director forwards a request."""
    try:
        from accounts.models import User, UserRole
        from accounts.notifications import _send, _base_html, SITE_URL

        csos = User.objects.filter(
            role=UserRole.CHIEF_SPORTS_OFFICER, is_active=True
        ).values_list('email', flat=True)
        if not csos:
            return

        body = f"""
<p>The Director of Sports has forwarded an outside-Ligi player request for your final approval.</p>
<dl class="info-box">
  <dt>Player</dt><dd>{request_obj.player_name} (ID: {request_obj.national_id})</dd>
  <dt>Ward All Stars Team</dt><dd>{request_obj.ward_allstars.official_name}</dd>
  <dt>Director's Notes</dt><dd>{request_obj.director_notes or 'None'}</dd>
  <dt>Justification</dt><dd>{request_obj.justification}</dd>
</dl>
<a href="{SITE_URL}/portal/cso/outside-ligi-requests/{request_obj.pk}/" class="btn">Review &amp; Decide</a>"""
        _send(
            f"Outside-Ligi Request Forwarded — {request_obj.ward_allstars.official_name}",
            _base_html("Outside-Ligi Player Request — Final Approval", body),
            list(csos),
        )
    except Exception as exc:
        logger.warning("Failed to notify CSO of outside-Ligi request: %s", exc)


def _notify_tm_outside_ligi_decision(request_obj, approved, player=None):
    """Email the Ward All Stars TM about the final decision."""
    try:
        from accounts.notifications import _send, _base_html, SITE_URL

        tm = request_obj.ward_allstars.appointed_tm_user
        if not tm or not tm.email:
            return

        if approved:
            body = f"""
<p>Dear <strong>{tm.first_name}</strong>,</p>
<p>Your request to include <strong>{request_obj.player_name}</strong> in the
{request_obj.ward_allstars.official_name} has been <strong style="color:#198754">approved</strong>
by the Chief Sports Officer.</p>
<p>The player has been added to your allstars longlist. Please update their contact details
in the portal.</p>
<a href="{SITE_URL}/ligi/allstars/longlist/" class="btn">View Longlist</a>"""
            subject = f"Outside-Ligi Player Approved — {request_obj.player_name}"
        else:
            reason = request_obj.cso_notes or request_obj.director_notes or "No reason provided"
            body = f"""
<p>Dear <strong>{tm.first_name}</strong>,</p>
<p>Your request to include <strong>{request_obj.player_name}</strong> in the
{request_obj.ward_allstars.official_name} has been <strong style="color:#dc3545">rejected</strong>.</p>
<div class="alert">Reason: {reason}</div>
<p>Contact the sports office if you have any questions.</p>"""
            subject = f"Outside-Ligi Player Request Rejected — {request_obj.player_name}"

        _send(subject, _base_html("Outside-Ligi Player Request Decision", body), [tm.email])
    except Exception as exc:
        logger.warning("Failed to notify TM of outside-Ligi decision: %s", exc)
