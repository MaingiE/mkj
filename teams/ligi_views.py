"""
MKJ SUPA CUP - Ligi Mashinani Public Registration View
Handles the AJAX form submission from the homepage panel.
"""
import json
import logging
import re

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError

from accounts.models import MAKUENI_SUBCOUNTY_WARDS, normalize_kenya_phone
from .models import LigiMashinaniRegistration, LIGI_DISCIPLINE_CHOICES

logger = logging.getLogger(__name__)

# Valid sub-counties for Makueni
VALID_SUB_COUNTIES = list(MAKUENI_SUBCOUNTY_WARDS.keys())

DISCIPLINE_KEYS = {d[0] for d in LIGI_DISCIPLINE_CHOICES}


def _validate_phone(raw):
    """Normalise and validate a Kenyan phone number. Returns +254XXXXXXXXX or raises ValueError."""
    normalized = normalize_kenya_phone(raw or "")
    if not normalized:
        raise ValueError("Enter a valid Kenyan phone number (e.g. 0712345678 or +254712345678).")
    return normalized


def _validate_email(email):
    email = (email or "").strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise ValueError("Enter a valid email address.")
    return email


@require_POST
def ligi_register_view(request):
    """
    POST /ligi/register/
    Accepts JSON body with team + manager details.
    Returns JSON {success: true/false, message: "..."}.
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"success": False, "message": "Invalid request data."}, status=400)

    errors = {}

    # ── Sub-county & ward ─────────────────────────────────────────────────
    sub_county = (data.get("sub_county") or "").strip()
    ward       = (data.get("ward") or "").strip()

    if sub_county not in VALID_SUB_COUNTIES:
        errors["sub_county"] = "Select a valid Makueni sub-county."
    else:
        valid_wards = MAKUENI_SUBCOUNTY_WARDS.get(sub_county, [])
        if ward not in valid_wards:
            errors["ward"] = "Select a valid ward for the chosen sub-county."

    # ── Team details ──────────────────────────────────────────────────────
    team_name  = (data.get("team_name") or "").strip()
    discipline = (data.get("discipline") or "").strip()

    if not team_name:
        errors["team_name"] = "Team name is required."
    elif len(team_name) < 3:
        errors["team_name"] = "Team name must be at least 3 characters."

    if discipline not in DISCIPLINE_KEYS:
        errors["discipline"] = "Select a valid sport discipline."

    # ── Manager details ───────────────────────────────────────────────────
    first_name = (data.get("manager_first_name") or "").strip()
    last_name  = (data.get("manager_last_name") or "").strip()

    if not first_name:
        errors["manager_first_name"] = "First name is required."
    if not last_name:
        errors["manager_last_name"] = "Last name is required."

    raw_email = data.get("manager_email", "")
    try:
        email = _validate_email(raw_email)
    except ValueError as exc:
        errors["manager_email"] = str(exc)
        email = ""

    raw_phone = data.get("manager_phone", "")
    try:
        phone = _validate_phone(raw_phone)
    except ValueError as exc:
        errors["manager_phone"] = str(exc)
        phone = ""

    if errors:
        return JsonResponse({"success": False, "errors": errors}, status=422)

    # ── Duplicate checks ──────────────────────────────────────────────────
    if email and LigiMashinaniRegistration.objects.filter(manager_email__iexact=email).exists():
        return JsonResponse({
            "success": False,
            "errors": {
                "manager_email": "A registration with this email already exists. Please log in or contact support."
            },
        }, status=422)

    # ── Create the registration ───────────────────────────────────────────
    try:
        reg = LigiMashinaniRegistration.objects.create(
            sub_county=sub_county,
            ward=ward,
            team_name=team_name,
            discipline=discipline,
            manager_first_name=first_name,
            manager_last_name=last_name,
            manager_email=email,
            manager_phone=phone,
        )
        logger.info(
            "Ligi Mashinani registration submitted: %s | %s, %s | %s | ref=%d",
            team_name, ward, sub_county, discipline, reg.pk,
        )
    except Exception as exc:
        logger.exception("Failed to save Ligi Mashinani registration: %s", exc)
        return JsonResponse({
            "success": False,
            "message": "An unexpected error occurred. Please try again.",
        }, status=500)

    return JsonResponse({
        "success": True,
        "message": (
            f"Registration submitted for <strong>{team_name}</strong>! "
            f"Your application is pending ward sports council verification. "
            f"You will receive login credentials at <strong>{email}</strong> once approved."
        ),
        "ref": reg.pk,
    })
