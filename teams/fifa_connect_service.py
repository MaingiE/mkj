"""
MKJ SUPA CUP — FIFA Connect API Integration Service
==============================================
Checks whether a player is registered in higher-level leagues above
County League. Players found in any of these leagues are FLAGGED and
cannot participate in MKJ SUPA CUP county-level competitions:

  • Regional League
  • Division Two
  • Division One
  • National Super League
  • Kenya FKF Premier League (current or former)

This module provides a pluggable service. In production, replace the
`_call_fifa_connect_api()` method with real HTTP calls to the FIFA
Connect / FKF Player Registration API.

Usage:
    from teams.fifa_connect_service import FIFAConnectService
    svc = FIFAConnectService()
    result = svc.check_player(player)  # returns FIFAConnectResult
"""
import logging
import hashlib
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# ── Higher-level leagues that disqualify from county competition ──────────────
HIGHER_LEAGUES = [
    "Regional League",
    "Division Two",
    "Division One",
    "National Super League",
    "Kenya FKF Premier League",
]


@dataclass
class FIFAConnectResult:
    """Immutable result from a FIFA Connect lookup."""
    success: bool                      # API call succeeded
    player_found: bool = False         # Player exists in FIFA Connect
    fifa_connect_id: str = ""          # FIFA Connect Player ID
    leagues_found: List[str] = field(default_factory=list)
    is_flagged: bool = False           # True if registered in higher league
    flag_reason: str = ""              # Human-readable reason
    raw_response: dict = field(default_factory=dict)
    error_message: str = ""
    checked_at: Optional[datetime] = None

    @property
    def is_clear(self) -> bool:
        """Player is clear to participate (no higher leagues)."""
        return self.success and self.player_found and not self.is_flagged


class FIFAConnectService:
    """
    Service class for FIFA Connect Player Registry checks.

    In production, set these in Django settings or .env:
        FIFA_CONNECT_API_URL   = "https://api.fifaconnect.ke/v1"
        FIFA_CONNECT_API_KEY   = "<your-api-key>"
        FIFA_CONNECT_ENABLED   = True
    """

    def __init__(self):
        self.api_url = getattr(settings, 'FIFA_CONNECT_API_URL', 'https://api.fifaconnect.ke/v1')
        self.api_key = getattr(settings, 'FIFA_CONNECT_API_KEY', '')
        self.enabled = getattr(settings, 'FIFA_CONNECT_ENABLED', True)
        self.timeout = getattr(settings, 'FIFA_CONNECT_TIMEOUT', 30)

    # ──────────────────────────────────────────────────────────────────────────
    #  Public API
    # ──────────────────────────────────────────────────────────────────────────

    def check_player(self, player) -> FIFAConnectResult:
        """
        Check a player against the FIFA Connect registry.

        Args:
            player: teams.Player instance (needs first_name, last_name,
                    date_of_birth, national_id_number, fifa_connect_id)

        Returns:
            FIFAConnectResult with the lookup outcome.
        """
        now = timezone.now()

        if not self.enabled:
            return FIFAConnectResult(
                success=False,
                error_message="FIFA Connect integration is disabled.",
                checked_at=now,
            )

        try:
            raw = self._call_fifa_connect_api(player)
            return self._parse_response(raw, now)
        except Exception as exc:
            logger.exception("FIFA Connect API error for player %s", player.pk)
            return FIFAConnectResult(
                success=False,
                error_message=str(exc),
                checked_at=now,
            )

    def check_player_by_data(self, first_name: str, last_name: str,
                              date_of_birth: str, national_id: str = "",
                              fifa_id: str = "") -> FIFAConnectResult:
        """
        Check using raw data (useful for pre-registration screening).
        """
        now = timezone.now()

        if not self.enabled:
            return FIFAConnectResult(
                success=False,
                error_message="FIFA Connect integration is disabled.",
                checked_at=now,
            )

        try:
            payload = {
                "first_name": first_name,
                "last_name": last_name,
                "date_of_birth": str(date_of_birth),
                "national_id": national_id,
                "fifa_connect_id": fifa_id,
            }
            raw = self._call_api(payload)
            return self._parse_response(raw, now)
        except Exception as exc:
            logger.exception("FIFA Connect API error")
            return FIFAConnectResult(
                success=False,
                error_message=str(exc),
                checked_at=now,
            )

    def bulk_check(self, players) -> dict:
        """
        Check multiple players. Returns {player_pk: FIFAConnectResult}.
        """
        results = {}
        for player in players:
            results[player.pk] = self.check_player(player)
        return results

    # ──────────────────────────────────────────────────────────────────────────
    #  Private — API communication
    # ──────────────────────────────────────────────────────────────────────────

    def _call_fifa_connect_api(self, player) -> dict:
        """
        Call the FIFA Connect API for a given Player model instance.

        PRODUCTION: Replace the body of this method with real HTTP calls:
            import requests
            resp = requests.post(
                f"{self.api_url}/players/search",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        """
        payload = {
            "first_name": player.first_name,
            "last_name": player.last_name,
            "date_of_birth": str(player.date_of_birth),
            "national_id": player.national_id_number,
            "fifa_connect_id": player.fifa_connect_id,
        }
        return self._call_api(payload)

    def _call_api(self, payload: dict) -> dict:
        """
        Stub implementation — simulates the FIFA Connect API response.

        In PRODUCTION, this will be an HTTP call. For now, it returns a
        simulated response based on the player data so the workflow can
        be tested end-to-end.
        """
        if self.api_key:
            # ── REAL API CALL (uncomment when API credentials are available) ──
            # import requests
            # resp = requests.post(
            #     f"{self.api_url}/players/search",
            #     headers={
            #         "Authorization": f"Bearer {self.api_key}",
            #         "Content-Type": "application/json",
            #     },
            #     json=payload,
            #     timeout=self.timeout,
            # )
            # resp.raise_for_status()
            # return resp.json()
            pass

        # ── SIMULATION MODE (for development/testing) ─────────────────────────
        # Generates a deterministic FIFA ID and returns "clear" by default.
        # Admins can manually flag players after reviewing the result.
        logger.info("FIFA Connect SIMULATION mode — player: %s %s",
                     payload.get('first_name'), payload.get('last_name'))

        # Generate a consistent simulated FIFA ID
        seed = f"{payload.get('first_name', '')}{payload.get('last_name', '')}{payload.get('date_of_birth', '')}"
        sim_id = payload.get('fifa_connect_id') or f"KE-{hashlib.md5(seed.encode()).hexdigest()[:8].upper()}"

        return {
            "status": "success",
            "player_found": True,
            "fifa_connect_id": sim_id,
            "full_name": f"{payload.get('first_name', '')} {payload.get('last_name', '')}",
            "date_of_birth": payload.get('date_of_birth', ''),
            "national_id": payload.get('national_id', ''),
            "registrations": [],  # No higher-league registrations in simulation
            "_simulation": True,
        }

    def _parse_response(self, raw: dict, checked_at) -> FIFAConnectResult:
        """Parse the API response into a FIFAConnectResult."""
        if raw.get("status") != "success":
            return FIFAConnectResult(
                success=False,
                error_message=raw.get("error", "Unknown API error"),
                raw_response=raw,
                checked_at=checked_at,
            )

        player_found = raw.get("player_found", False)
        fifa_id = raw.get("fifa_connect_id", "")
        registrations = raw.get("registrations", [])

        # Check for higher-league registrations
        leagues_found = []
        for reg in registrations:
            league_name = reg.get("league", "")
            status = reg.get("status", "").lower()
            # Flag both current and former registrations
            if any(hl.lower() in league_name.lower() for hl in HIGHER_LEAGUES):
                leagues_found.append({
                    "league": league_name,
                    "season": reg.get("season", ""),
                    "status": status,
                    "club": reg.get("club", ""),
                })

        is_flagged = len(leagues_found) > 0
        flag_reason = ""
        if is_flagged:
            league_names = [l["league"] for l in leagues_found]
            flag_reason = (
                f"Player registered in higher-level league(s): "
                f"{', '.join(league_names)}. Cannot participate in county competition."
            )

        return FIFAConnectResult(
            success=True,
            player_found=player_found,
            fifa_connect_id=fifa_id,
            leagues_found=leagues_found,
            is_flagged=is_flagged,
            flag_reason=flag_reason,
            raw_response=raw,
            checked_at=checked_at,
        )
