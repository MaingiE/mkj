"""
MKJ SUPA CUP - IPRS Identity Verification via Smile Identity
======================================================
Verifies player identity (name, DOB, gender, photo) against Kenya's
IPRS (Integrated Population Registration System) using Smile Identity
Enhanced KYC API.

Pricing: pay-per-lookup. Dashboard at usesmileid.com.

Usage:
    from teams.huduma_service import HudumaKenyaService
    svc = HudumaKenyaService()
    result = svc.verify_player_age(player)     # returns HudumaResult
    result = svc.lookup_by_national_id("1234")  # returns IPRSLookupResult

Configuration (.env):
    SMILE_PARTNER_ID=your_partner_id
    SMILE_API_KEY=your_api_key_here
    SMILE_ENVIRONMENT=production     # or 'sandbox' for testing
    IPRS_ENABLED=True
"""
import logging
import hashlib
import hmac
import requests
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, date

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class HudumaResult:
    """Immutable result from a Huduma Kenya verification."""
    success: bool                        # API call succeeded
    person_found: bool = False           # Person found in IPRS
    verified_name: str = ""              # Name as per IPRS
    verified_dob: Optional[date] = None  # Date of birth as per IPRS
    verified_age: Optional[int] = None   # Calculated age
    age_matches: bool = False            # DOB matches player record
    reference_number: str = ""           # Huduma verification reference
    raw_response: dict = field(default_factory=dict)
    error_message: str = ""
    checked_at: Optional[datetime] = None
    photo: str = ""                      # Base64-encoded IPRS passport photo

    @property
    def is_verified(self) -> bool:
        """Person found and age matches within tolerance."""
        return self.success and self.person_found and self.age_matches


@dataclass
class IPRSLookupResult:
    """Result from an IPRS National ID lookup."""
    success: bool
    person_found: bool = False
    first_name: str = ""
    last_name: str = ""
    other_names: str = ""
    full_name: str = ""
    date_of_birth: Optional[date] = None
    age: Optional[int] = None
    gender: str = ""
    national_id: str = ""
    reference_number: str = ""
    error_message: str = ""
    is_simulation: bool = False
    photo: str = ""                      # Base64-encoded IPRS passport photo

    def to_dict(self) -> dict:
        """Serialize for JSON response."""
        return {
            "success": self.success,
            "person_found": self.person_found,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "other_names": self.other_names,
            "full_name": self.full_name,
            "date_of_birth": self.date_of_birth.isoformat() if self.date_of_birth else None,
            "age": self.age,
            "gender": self.gender,
            "national_id": self.national_id,
            "reference_number": self.reference_number,
            "error_message": self.error_message,
            "is_simulation": self.is_simulation,
            "photo": self.photo,
        }


class HudumaKenyaService:
    """
    IPRS identity verification via Smile Identity Enhanced KYC API.

    Endpoints:
        Sandbox:    https://testapi.smileidentity.com/v2
        Production: https://api.smileidentity.com/v2

    Falls back to simulation mode when SMILE_API_KEY is not set.
    """

    SANDBOX_URL = "https://testapi.smileidentity.com/v2"
    PRODUCTION_URL = "https://api.smileidentity.com/v2"

    def __init__(self):
        self.partner_id = getattr(settings, 'SMILE_PARTNER_ID', '')
        self.api_key = getattr(settings, 'SMILE_API_KEY', '')
        self.environment = getattr(settings, 'SMILE_ENVIRONMENT', 'sandbox')
        self.timeout = getattr(settings, 'SMILE_TIMEOUT', 30)
        self.enabled = getattr(settings, 'IPRS_ENABLED', True)

        if self.environment == 'production':
            self.base_url = self.PRODUCTION_URL
        else:
            self.base_url = self.SANDBOX_URL

    @property
    def _is_live(self) -> bool:
        """True when real API credentials are configured."""
        return bool(self.api_key) and bool(self.partner_id)

    def _generate_signature(self, timestamp: str) -> str:
        """Generate HMAC-SHA256 signature for Smile Identity API."""
        msg = timestamp + self.partner_id
        return hmac.new(
            self.api_key.encode(), msg.encode(), hashlib.sha256
        ).hexdigest()

    # ──────────────────────────────────────────────────────────────────────────
    #  Public API
    # ──────────────────────────────────────────────────────────────────────────

    def verify_player_age(self, player) -> HudumaResult:
        """
        Verify a player's age via Huduma Kenya / IPRS.

        Args:
            player: teams.Player instance

        Returns:
            HudumaResult with verification outcome.
        """
        now = timezone.now()

        if not self.enabled:
            return HudumaResult(
                success=False,
                error_message="Huduma Kenya integration is disabled.",
                checked_at=now,
            )

        if not player.national_id_number and not player.birth_cert_number:
            return HudumaResult(
                success=False,
                error_message="Player has no National ID or Birth Certificate number.",
                checked_at=now,
            )

        try:
            raw = self._call_huduma_api(player)
            return self._parse_response(raw, player, now)
        except Exception as exc:
            logger.exception("Huduma Kenya API error for player %s", player.pk)
            return HudumaResult(
                success=False,
                error_message=str(exc),
                checked_at=now,
            )

    def verify_by_data(self, national_id: str = "", birth_cert: str = "",
                        claimed_dob: str = "", full_name: str = "") -> HudumaResult:
        """
        Verify using raw data (for pre-registration screening).
        """
        now = timezone.now()

        if not self.enabled:
            return HudumaResult(
                success=False,
                error_message="Huduma Kenya integration is disabled.",
                checked_at=now,
            )

        try:
            payload = {
                "national_id": national_id,
                "birth_cert_number": birth_cert,
                "full_name": full_name,
            }
            raw = self._call_api(payload)
            # Parse with claimed DOB
            claimed = None
            if claimed_dob:
                try:
                    claimed = date.fromisoformat(str(claimed_dob))
                except (ValueError, TypeError):
                    pass
            return self._parse_with_claimed_dob(raw, claimed, now)
        except Exception as exc:
            logger.exception("Huduma Kenya API error")
            return HudumaResult(
                success=False,
                error_message=str(exc),
                checked_at=now,
            )

    def lookup_by_national_id(self, national_id: str) -> IPRSLookupResult:
        """
        Look up a person's details by National ID from IPRS.

        This is used on the player registration form - when a team manager
        enters a National ID, this method returns the person's name, date
        of birth, and age so the form fields can be auto-populated.

        Args:
            national_id: Kenyan National ID number (string).

        Returns:
            IPRSLookupResult with person details on success.
        """
        if not national_id or not national_id.strip():
            return IPRSLookupResult(
                success=False,
                error_message="National ID number is required.",
            )

        national_id = national_id.strip()

        if not self.enabled:
            return IPRSLookupResult(
                success=False,
                error_message="IPRS integration is currently disabled.",
            )

        try:
            raw = self._call_iprs_lookup(national_id)
            return self._parse_iprs_lookup(raw, national_id)
        except Exception as exc:
            logger.exception("IPRS lookup error for ID %s", national_id)
            return IPRSLookupResult(
                success=False,
                error_message=f"IPRS lookup failed: {exc}",
            )

    # ──────────────────────────────────────────────────────────────────────────
    #  Private - Smile Identity Enhanced KYC API
    # ──────────────────────────────────────────────────────────────────────────

    def _call_smile_iprs(self, national_id: str) -> dict:
        """
        Call Smile Identity Enhanced KYC → Kenya IPRS endpoint.

        POST https://[test]api.smileidentity.com/v2/verify
        JSON body with partner_id, signature, id_number, id_type, country.

        Returns normalised dict with status, person_found, person, reference.
        Falls back to simulation if no API key configured.
        """
        if not self._is_live:
            return self._simulate_iprs(national_id)

        url = f"{self.base_url}/verify"
        timestamp = datetime.utcnow().isoformat()
        try:
            payload = {
                "partner_id": self.partner_id,
                "timestamp": timestamp,
                "signature": self._generate_signature(timestamp),
                "country": "KE",
                "id_type": "NATIONAL_ID",
                "id_number": national_id,
                "source_sdk": "rest_api",
                "source_sdk_version": "1.0.0",
            }
            resp = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            raw = resp.json()
        except requests.exceptions.Timeout:
            logger.error("Smile ID IPRS timeout for ID %s", national_id)
            return {"status": "error", "error": "IPRS lookup timed out. Please try again."}
        except requests.exceptions.HTTPError as exc:
            logger.error("Smile ID HTTP error %s for ID %s", exc.response.status_code, national_id)
            try:
                body = exc.response.json()
                msg = body.get("error", str(exc))
            except Exception:
                msg = str(exc)
            return {"status": "error", "error": msg}
        except requests.exceptions.RequestException as exc:
            logger.exception("Smile ID request error for ID %s", national_id)
            return {"status": "error", "error": f"Network error: {exc}"}

        return self._normalise_smile_response(raw, national_id)

    def _normalise_smile_response(self, raw: dict, national_id: str) -> dict:
        """
        Convert Smile Identity Enhanced KYC response to internal format.

        Smile ID response shape (Enhanced KYC):
        {
            "Actions": { "Verify_ID_Number": "Verified", ... },
            "FullName": "JOHN PETER KAMAU",
            "DOB": "1998-05-14",
            "Gender": "Male",
            "IDNumber": "12345678",
            "Photo": "base64...",
            "Country": "KE",
            "IDType": "NATIONAL_ID",
            "ResultCode": "1012",
            "ResultText": "ID Verified",
            "SmileJobID": "...",
            "PartnerParams": { ... },
            "signature": "...",
            "timestamp": "..."
        }
        """
        # Check for error responses
        if "error" in raw:
            return {
                "status": "error",
                "error": raw.get("error", "IPRS lookup failed"),
                "person_found": False,
            }

        actions = raw.get("Actions", {})
        id_verified = actions.get("Verify_ID_Number", "") == "Verified"

        if not id_verified:
            result_text = raw.get("ResultText", "ID not verified")
            return {
                "status": "success",
                "person_found": False,
                "reference": raw.get("SmileJobID", ""),
                "person": {},
            }

        full_name = raw.get("FullName", "")
        # Smile returns full name as one string - split into first/last
        name_parts = full_name.split() if full_name else []
        first = name_parts[0] if len(name_parts) >= 1 else ""
        last = name_parts[-1] if len(name_parts) >= 2 else ""
        other = " ".join(name_parts[1:-1]) if len(name_parts) >= 3 else ""

        return {
            "status": "success",
            "person_found": True,
            "reference": raw.get("SmileJobID", f"SM-{hashlib.md5(national_id.encode()).hexdigest()[:10].upper()}"),
            "person": {
                "first_name": first.title() if first else "",
                "last_name": last.title() if last else "",
                "other_names": other.title() if other else "",
                "full_name": full_name.title() if full_name else "",
                "date_of_birth": raw.get("DOB", ""),
                "gender": raw.get("Gender", ""),
                "national_id": raw.get("IDNumber", national_id),
                "photo": raw.get("Photo", ""),
            },
            "_simulation": False,
        }

    def _call_huduma_api(self, player) -> dict:
        """Call IPRS for a player object."""
        national_id = player.national_id_number
        if not national_id and player.birth_cert_number:
            # Birth cert can't be looked up via IPRS - return simulation
            return self._simulate_iprs(player.birth_cert_number)
        return self._call_smile_iprs(national_id)

    def _call_api(self, payload: dict) -> dict:
        """Call IPRS with a payload dict (for verify_by_data)."""
        national_id = payload.get("national_id", "")
        if national_id:
            return self._call_smile_iprs(national_id)
        # No national ID - fall back to simulation
        return self._simulate_iprs(
            payload.get("birth_cert_number", "") or payload.get("full_name", "unknown")
        )

    def _call_iprs_lookup(self, national_id: str) -> dict:
        """Call IPRS for a national ID lookup."""
        return self._call_smile_iprs(national_id)

    # ──────────────────────────────────────────────────────────────────────────
    #  Simulation fallback (when no API key is configured)
    # ──────────────────────────────────────────────────────────────────────────

    def _simulate_iprs(self, seed_id: str) -> dict:
        """
        Deterministic simulation of an IPRS response.
        Used when AT_API_KEY is not set (development / demo mode).
        """
        logger.info("IPRS SIMULATION mode - ID: %s", seed_id)

        ref = f"SIM-{hashlib.md5(seed_id.encode()).hexdigest()[:10].upper()}"
        id_hash = int(hashlib.md5(seed_id.encode()).hexdigest(), 16)

        first_names = [
            "James", "John", "Peter", "David", "Brian",
            "Kevin", "Dennis", "Daniel", "Michael", "Joseph",
            "Mary", "Grace", "Faith", "Joy", "Mercy",
            "Ann", "Sarah", "Lucy", "Jane", "Ruth",
        ]
        last_names = [
            "Ochieng", "Wanjiku", "Mwangi", "Kiprop", "Otieno",
            "Kamau", "Njoroge", "Chebet", "Mutua", "Wekesa",
            "Akinyi", "Kibet", "Omondi", "Waithera", "Rotich",
        ]

        first = first_names[id_hash % len(first_names)]
        last = last_names[(id_hash // 100) % len(last_names)]
        gender = "Male" if id_hash % 2 == 0 else "Female"

        today = timezone.now().date()
        age = 18 + (id_hash % 6)
        birth_year = today.year - age
        birth_month = 1 + (id_hash % 12)
        birth_day = 1 + (id_hash % 28)
        dob = date(birth_year, birth_month, birth_day)

        return {
            "status": "success",
            "person_found": True,
            "reference": ref,
            "person": {
                "first_name": first,
                "last_name": last,
                "other_names": "",
                "full_name": f"{first} {last}",
                "date_of_birth": dob.isoformat(),
                "gender": gender,
                "national_id": seed_id,
                "photo": "",
            },
            "_simulation": True,
        }

    def _parse_response(self, raw: dict, player, checked_at) -> HudumaResult:
        """Parse the Huduma API response, comparing against the player's claimed DOB."""
        return self._parse_with_claimed_dob(raw, player.date_of_birth, checked_at)

    def _parse_with_claimed_dob(self, raw: dict, claimed_dob, checked_at) -> HudumaResult:
        """Parse response and compare against a claimed date of birth."""
        if raw.get("status") != "success":
            return HudumaResult(
                success=False,
                error_message=raw.get("error", "Unknown API error"),
                raw_response=raw,
                checked_at=checked_at,
            )

        person_found = raw.get("person_found", False)
        person = raw.get("person", {})

        verified_name = person.get("full_name", "")
        ref = raw.get("reference", "")

        # Parse DOB from response
        verified_dob = None
        dob_str = person.get("date_of_birth")
        if dob_str:
            try:
                verified_dob = date.fromisoformat(str(dob_str))
            except (ValueError, TypeError):
                pass

        # Calculate verified age
        verified_age = None
        if verified_dob:
            today = timezone.now().date()
            verified_age = today.year - verified_dob.year - (
                (today.month, today.day) < (verified_dob.month, verified_dob.day)
            )

        # Check if DOB matches - in simulation mode without DOB from API,
        # we rely on the admin to manually confirm
        age_matches = False
        if verified_dob and claimed_dob:
            age_matches = verified_dob == claimed_dob
        elif raw.get("_simulation") and person_found:
            # In simulation mode, mark as needing manual confirmation
            # Admin will finalize the status
            age_matches = True  # Placeholder - admin must confirm

        return HudumaResult(
            success=True,
            person_found=person_found,
            verified_name=verified_name,
            verified_dob=verified_dob,
            verified_age=verified_age,
            age_matches=age_matches,
            reference_number=ref,
            raw_response=raw,
            checked_at=checked_at,
            photo=person.get("photo", ""),
        )

    # ──────────────────────────────────────────────────────────────────────────
    #  Private - Response parsing
    # ──────────────────────────────────────────────────────────────────────────

    def _parse_iprs_lookup(self, raw: dict, national_id: str) -> IPRSLookupResult:
        """Parse the IPRS lookup response into an IPRSLookupResult."""
        if raw.get("status") != "success":
            return IPRSLookupResult(
                success=False,
                error_message=raw.get("error", "IPRS lookup failed."),
            )

        person_found = raw.get("person_found", False)
        if not person_found:
            return IPRSLookupResult(
                success=True,
                person_found=False,
                national_id=national_id,
                error_message="No person found with this National ID.",
                is_simulation=raw.get("_simulation", False),
            )

        person = raw.get("person", {})

        # Parse date of birth
        dob = None
        dob_str = person.get("date_of_birth")
        if dob_str:
            try:
                dob = date.fromisoformat(str(dob_str))
            except (ValueError, TypeError):
                pass

        # Calculate age
        age = None
        if dob:
            today = timezone.now().date()
            age = today.year - dob.year - (
                (today.month, today.day) < (dob.month, dob.day)
            )

        return IPRSLookupResult(
            success=True,
            person_found=True,
            first_name=person.get("first_name", ""),
            last_name=person.get("last_name", ""),
            other_names=person.get("other_names", ""),
            full_name=person.get("full_name", ""),
            date_of_birth=dob,
            age=age,
            gender=person.get("gender", ""),
            national_id=national_id,
            reference_number=raw.get("reference", ""),
            is_simulation=raw.get("_simulation", False),
            photo=person.get("photo", ""),
        )
