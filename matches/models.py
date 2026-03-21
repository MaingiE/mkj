"""
MKJ SUPA CUP Matches — Models (Squad Submissions, Match Reports, Results)
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


# ═══════════════════════════════════════════════════════════════════════════════
#   SPORT-SPECIFIC CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

def _football_sports():
    return {"football_men", "football_women"}

def _volleyball_sports():
    return {"volleyball_men", "volleyball_women", "beach_volleyball"}

def _basketball5_sports():
    return {"basketball_men", "basketball_women", "basketball"}

def _basketball3_sports():
    return {"basketball_3x3_men", "basketball_3x3_women", "basketball_3x3"}

def _handball_sports():
    return {"handball_men", "handball_women", "handball", "beach_handball"}


def get_sport_family(sport_type):
    """Return the sport family string for a given sport_type value."""
    if sport_type in _football_sports():
        return "football"
    if sport_type in _volleyball_sports():
        return "volleyball"
    if sport_type in _basketball5_sports():
        return "basketball_5x5"
    if sport_type in _basketball3_sports():
        return "basketball_3x3"
    if sport_type in _handball_sports():
        return "handball"
    return "football"  # default fallback


# Per-sport match configuration
SPORT_CONFIG = {
    "football": {
        "label": "Soccer",
        "periods": 2,
        "period_label": "Half",
        "period_labels": ["1st Half", "2nd Half"],
        "default_duration": 90,
        "has_extra_time": True,
        "has_penalties": True,
        "score_unit": "goals",
        "event_types": [
            ("goal", "Goal"), ("assist", "Assist"),
            ("yellow", "Yellow Card"), ("red", "Red Card"),
            ("second_yellow", "Second Yellow (Red)"),
            ("sub_on", "Substitution On"), ("sub_off", "Substitution Off"),
            ("injury", "Injury"),
            ("penalty", "Penalty Goal"), ("penalty_miss", "Penalty Missed"),
            ("og", "Own Goal"),
        ],
        "standings_points": {"win": 3, "draw": 1, "loss": 0},
    },
    "volleyball": {
        "label": "Volleyball",
        "periods": 5,
        "period_label": "Set",
        "period_labels": ["Set 1", "Set 2", "Set 3", "Set 4", "Set 5"],
        "default_duration": 0,  # no fixed duration
        "has_extra_time": False,
        "has_penalties": False,
        "score_unit": "points",
        "event_types": [
            ("yellow", "Yellow Card (Warning)"),
            ("red", "Red Card (Penalty)"),
            ("expulsion", "Expulsion"),
            ("sub_on", "Substitution On"), ("sub_off", "Substitution Off"),
            ("injury", "Injury"), ("timeout", "Timeout"),
        ],
        "standings_points": {
            "win_3_0": 3, "win_3_1": 3,
            "win_3_2": 2, "loss_2_3": 1,
            "loss_1_3": 0, "loss_0_3": 0,
        },
    },
    "basketball_5x5": {
        "label": "Basketball 5×5",
        "periods": 4,
        "period_label": "Quarter",
        "period_labels": ["Q1", "Q2", "Q3", "Q4"],
        "default_duration": 40,
        "has_extra_time": True,  # overtime periods
        "has_penalties": False,
        "score_unit": "points",
        "event_types": [
            ("two_pointer", "2-Point Field Goal"), ("three_pointer", "3-Point Field Goal"),
            ("free_throw", "Free Throw Made"), ("free_throw_miss", "Free Throw Missed"),
            ("foul", "Personal Foul"), ("tech_foul", "Technical Foul"),
            ("unsportsmanlike", "Unsportsmanlike Foul"), ("disqualifying", "Disqualifying Foul"),
            ("sub_on", "Substitution On"), ("sub_off", "Substitution Off"),
            ("timeout", "Timeout"), ("injury", "Injury"),
        ],
        "standings_points": {"win": 2, "loss": 1},
    },
    "basketball_3x3": {
        "label": "Basketball 3×3",
        "periods": 1,
        "period_label": "Period",
        "period_labels": ["Regulation"],
        "default_duration": 10,
        "has_extra_time": True,  # OT first to 2
        "has_penalties": False,
        "score_unit": "points",
        "event_types": [
            ("one_pointer", "1-Point Shot (Inside Arc)"),
            ("two_pointer", "2-Point Shot (Outside Arc)"),
            ("free_throw", "Free Throw Made"), ("free_throw_miss", "Free Throw Missed"),
            ("foul", "Personal Foul"), ("tech_foul", "Technical Foul"),
            ("sub_on", "Substitution On"), ("sub_off", "Substitution Off"),
            ("timeout", "Timeout"), ("injury", "Injury"),
        ],
        "standings_points": {"win": 2, "loss": 1},
    },
    "handball": {
        "label": "Handball",
        "periods": 2,
        "period_label": "Half",
        "period_labels": ["1st Half", "2nd Half"],
        "default_duration": 60,
        "has_extra_time": True,   # 2×5 min
        "has_penalties": True,    # 7-metre throw shootout
        "score_unit": "goals",
        "event_types": [
            ("goal", "Goal"), ("assist", "Assist"),
            ("seven_m_goal", "7m Throw Goal"), ("seven_m_miss", "7m Throw Missed"),
            ("yellow", "Yellow Card (Warning)"),
            ("two_min", "2-Minute Suspension"),
            ("red", "Red Card (Disqualification)"),
            ("blue_card", "Blue Card (Report)"),
            ("sub_on", "Substitution On"), ("sub_off", "Substitution Off"),
            ("injury", "Injury"), ("timeout", "Team Timeout"),
        ],
        "standings_points": {"win": 2, "draw": 1, "loss": 0},
    },
}


def get_sport_config(sport_type):
    """Return sport config dict for a given sport_type value."""
    family = get_sport_family(sport_type)
    return SPORT_CONFIG.get(family, SPORT_CONFIG["football"])


def get_event_types_for_sport(sport_type):
    """Return the list of event type tuples for a sport."""
    cfg = get_sport_config(sport_type)
    return cfg["event_types"]


# ── Sport-specific match-day starters ────────────────────────────────────────
SPORT_STARTERS = {
    "football_men": 11, "football_women": 11,
    "volleyball_men": 6, "volleyball_women": 6,
    "basketball_men": 5, "basketball_women": 5,
    "basketball_3x3_men": 3, "basketball_3x3_women": 3,
    "handball_men": 7, "handball_women": 7,
    "beach_volleyball": 2, "beach_handball": 4,
}

# ── Sport-specific squad rules (international guidelines) ────────────────────
# max_squad  = total players allowed on team list (starters + subs)
# max_subs   = maximum substitute players on the team list
# normal_sub_limit = number of normal substitutions allowed per match
# sub_windows = substitution windows allowed (excluding half-time); None = unlimited
# concussion_sub = whether an additional concussion substitution is allowed
SPORT_SQUAD_RULES = {
    "football": {
        "max_squad": 23, "max_subs": 12, "min_starters": 7,
        "normal_sub_limit": 5, "sub_windows": 3,
        "concussion_sub": True, "concussion_sub_grants_opponent_extra": True,
    },
    "volleyball": {
        "max_squad": 14, "max_subs": 8, "min_starters": 6,
        "normal_sub_limit": 6, "sub_windows": None,  # per set, unlimited windows
        "concussion_sub": False, "concussion_sub_grants_opponent_extra": False,
    },
    "basketball_5x5": {
        "max_squad": 12, "max_subs": 7, "min_starters": 5,
        "normal_sub_limit": None, "sub_windows": None,  # unlimited
        "concussion_sub": False, "concussion_sub_grants_opponent_extra": False,
    },
    "basketball_3x3": {
        "max_squad": 4, "max_subs": 1, "min_starters": 3,
        "normal_sub_limit": None, "sub_windows": None,  # unlimited
        "concussion_sub": False, "concussion_sub_grants_opponent_extra": False,
    },
    "handball": {
        "max_squad": 16, "max_subs": 9, "min_starters": 7,
        "normal_sub_limit": None, "sub_windows": None,  # unlimited
        "concussion_sub": False, "concussion_sub_grants_opponent_extra": False,
    },
}


def get_squad_rules(sport_type):
    """Return the squad rules dict for a sport type."""
    family = get_sport_family(sport_type)
    return SPORT_SQUAD_RULES.get(family, SPORT_SQUAD_RULES["football"])


def get_starters_for_sport(sport_type):
    """Return the required number of starters for a sport type."""
    return SPORT_STARTERS.get(sport_type, 11)


class SquadStatus(models.TextChoices):
    DRAFT     = "draft",     "Draft"
    SUBMITTED = "submitted", "Submitted"
    APPROVED  = "approved",  "Approved by Referee"
    REJECTED  = "rejected",  "Rejected — Needs Changes"


class SquadSubmission(models.Model):
    """
    Team Manager submits squad; Referee approves it before kick-off.
    Must be submitted at least 4 hours before kick-off (enforced in serializer).
    """
    FOOTBALL_FORMATIONS = [
        ("4-4-2",   "4-4-2"),
        ("4-3-3",   "4-3-3"),
        ("4-2-3-1", "4-2-3-1"),
        ("3-5-2",   "3-5-2"),
        ("4-5-1",   "4-5-1"),
        ("3-4-3",   "3-4-3"),
        ("5-3-2",   "5-3-2"),
        ("5-4-1",   "5-4-1"),
        ("4-1-4-1", "4-1-4-1"),
        ("4-3-2-1", "4-3-2-1"),
        ("4-1-2-1-2", "4-1-2-1-2"),
        ("3-4-1-2", "3-4-1-2"),
    ]

    KIT_CHOICES = [
        ("home", "Home Kit"),
        ("away", "Away Kit"),
        ("third", "Third Kit"),
    ]

    fixture     = models.ForeignKey(
        "competitions.Fixture", on_delete=models.CASCADE,
        related_name="squads"
    )
    team        = models.ForeignKey(
        "teams.Team", on_delete=models.CASCADE,
        related_name="squad_submissions"
    )
    status      = models.CharField(max_length=20, choices=SquadStatus.choices, default=SquadStatus.DRAFT)
    formation   = models.CharField(
        max_length=20, blank=True, default="",
        help_text="Playing formation (e.g. 4-3-3, 4-4-2) — applies to football",
    )
    kit_choice  = models.CharField(
        max_length=10, choices=KIT_CHOICES, default="home",
        help_text="Which kit the team will wear",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="squads_reviewed"
    )
    reviewed_at  = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    class Meta:
        unique_together = ["fixture", "team"]
        verbose_name = "Team List"
        verbose_name_plural = "Team Lists"

    def __str__(self):
        return f"{self.team} team list for {self.fixture}"


class SquadPlayer(models.Model):
    """Individual player entry in a squad submission."""
    submission   = models.ForeignKey(SquadSubmission, on_delete=models.CASCADE, related_name="squad_players")
    player       = models.ForeignKey("teams.Player", on_delete=models.CASCADE)
    is_starter   = models.BooleanField(default=True)
    shirt_number = models.PositiveIntegerField()  # May differ from regular number

    class Meta:
        unique_together = ["submission", "player"]
        ordering        = ["-is_starter", "shirt_number"]

    def __str__(self):
        role = "Starter" if self.is_starter else "Sub"
        return f"#{self.shirt_number} {self.player.get_full_name()} ({role})"


# ═══════════════════════════════════════════════════════════════════════════════
#   SUBSTITUTION REQUEST (procedural, 4th-official / referee approved)
# ═══════════════════════════════════════════════════════════════════════════════

class SubstitutionType(models.TextChoices):
    NORMAL      = "normal",      "Normal Substitution"
    CONCUSSION  = "concussion",  "Concussion Substitution"


class SubstitutionStatus(models.TextChoices):
    REQUESTED = "requested", "Requested"
    APPROVED  = "approved",  "Approved by 4th Official"
    EXECUTED  = "executed",  "Executed (Players Swapped)"
    DENIED    = "denied",    "Denied"


class SubstitutionRequest(models.Model):
    """
    Procedural substitution request per FIFA / FIVB / FIBA / IHF guidelines.

    Soccer (FIFA):
    - Up to 5 normal substitutions in 3 windows (+ half-time).
    - A 6th concussion substitution may be approved by the referee.
    - When a concussion sub is used, the opponent is awarded one extra substitution.

    Other sports: unlimited substitutions, no window restrictions.
    """
    fixture = models.ForeignKey(
        "competitions.Fixture", on_delete=models.CASCADE,
        related_name="substitution_requests",
    )
    team = models.ForeignKey(
        "teams.Team", on_delete=models.CASCADE,
        related_name="substitution_requests",
    )
    player_off = models.ForeignKey(
        "teams.Player", on_delete=models.CASCADE,
        related_name="subbed_off_requests",
        help_text="Player leaving the field",
    )
    player_on = models.ForeignKey(
        "teams.Player", on_delete=models.CASCADE,
        related_name="subbed_on_requests",
        help_text="Player entering the field",
    )
    minute = models.PositiveIntegerField(
        help_text="Match minute when the substitution is requested",
    )
    sub_type = models.CharField(
        max_length=12, choices=SubstitutionType.choices,
        default=SubstitutionType.NORMAL,
    )
    status = models.CharField(
        max_length=12, choices=SubstitutionStatus.choices,
        default=SubstitutionStatus.REQUESTED,
    )
    # Window tracking (soccer: max 3 windows excluding half-time)
    sub_window = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Substitution window number (soccer: 1-3). Null for sports with unlimited windows.",
    )
    # Concussion sub triggers an extra sub for the opponent (soccer)
    grants_opponent_extra = models.BooleanField(
        default=False,
        help_text="If True, this concussion sub awarded the opponent an additional substitution.",
    )
    reason = models.TextField(
        blank=True,
        help_text="Reason for substitution (required for concussion subs).",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="sub_requests_made",
        help_text="Team manager / bench official who requested the substitution.",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="sub_requests_approved",
        help_text="4th official (normal) or referee (concussion) who approved.",
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    denial_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["fixture", "team", "minute"]
        verbose_name = "Substitution Request"

    def __str__(self):
        return (
            f"Sub request: {self.player_off} → {self.player_on} "
            f"({self.get_sub_type_display()}, min {self.minute})"
        )

    @staticmethod
    def count_normal_subs_used(fixture, team):
        """Count executed normal substitutions for a team in a fixture."""
        return SubstitutionRequest.objects.filter(
            fixture=fixture, team=team,
            sub_type=SubstitutionType.NORMAL,
            status=SubstitutionStatus.EXECUTED,
        ).count()

    @staticmethod
    def count_concussion_subs_used(fixture, team):
        """Count executed concussion subs for a team in a fixture."""
        return SubstitutionRequest.objects.filter(
            fixture=fixture, team=team,
            sub_type=SubstitutionType.CONCUSSION,
            status=SubstitutionStatus.EXECUTED,
        ).count()

    @staticmethod
    def count_windows_used(fixture, team):
        """Count distinct substitution windows used (soccer only)."""
        return SubstitutionRequest.objects.filter(
            fixture=fixture, team=team,
            sub_type=SubstitutionType.NORMAL,
            status=SubstitutionStatus.EXECUTED,
            sub_window__isnull=False,
        ).values_list("sub_window", flat=True).distinct().count()

    @staticmethod
    def opponent_extra_subs_granted(fixture, team):
        """Count extra subs granted to a team because the opponent used concussion subs."""
        opponent_team = fixture.away_team if fixture.home_team == team else fixture.home_team
        return SubstitutionRequest.objects.filter(
            fixture=fixture, team=opponent_team,
            sub_type=SubstitutionType.CONCUSSION,
            status=SubstitutionStatus.EXECUTED,
            grants_opponent_extra=True,
        ).count()


class MatchReportStatus(models.TextChoices):
    DRAFT    = "draft",    "Draft"
    SUBMITTED = "submitted", "Submitted"
    APPROVED = "approved", "Approved"
    RETURNED = "returned", "Returned for Revision"


class MatchReport(models.Model):
    """
    Referee submits match report after the game.
    Referee Manager reviews and approves.
    """
    fixture      = models.OneToOneField(
        "competitions.Fixture", on_delete=models.CASCADE,
        related_name="match_report"
    )
    referee      = models.ForeignKey(
        "referees.RefereeProfile", on_delete=models.SET_NULL, null=True,
        related_name="match_reports"
    )
    appointment_snapshot = models.JSONField(
        default=list,
        blank=True,
        help_text="Snapshot of appointed officials for this fixture when the report was last saved.",
    )
    status       = models.CharField(max_length=20, choices=MatchReportStatus.choices, default=MatchReportStatus.DRAFT)

    # Final Score (total / aggregate — all sports)
    home_score   = models.PositiveIntegerField()
    away_score   = models.PositiveIntegerField()

    # Volleyball: sets won (e.g. 3-2)
    home_sets    = models.PositiveIntegerField(default=0, help_text="Sets/periods won by home team")
    away_sets    = models.PositiveIntegerField(default=0, help_text="Sets/periods won by away team")

    # Disciplinary
    home_yellow_cards = models.PositiveIntegerField(default=0)
    away_yellow_cards = models.PositiveIntegerField(default=0)
    home_red_cards    = models.PositiveIntegerField(default=0)
    away_red_cards    = models.PositiveIntegerField(default=0)

    # Handball: 2-minute suspensions
    home_suspensions  = models.PositiveIntegerField(default=0, help_text="2-minute suspensions (handball)")
    away_suspensions  = models.PositiveIntegerField(default=0, help_text="2-minute suspensions (handball)")

    # Report details
    match_duration  = models.PositiveIntegerField(default=90, help_text="Actual minutes played")
    added_time_ht   = models.PositiveIntegerField(default=0, help_text="Added time 1st half (mins)")
    added_time_ft   = models.PositiveIntegerField(default=0, help_text="Added time 2nd half (mins)")
    overtime_played = models.BooleanField(default=False, help_text="Was overtime/extra time played?")
    overtime_periods = models.PositiveIntegerField(default=0, help_text="Number of overtime periods played (basketball)")
    pitch_condition = models.CharField(max_length=20, choices=[
        ("excellent","Excellent"),("good","Good"),("fair","Fair"),("poor","Poor")
    ], default="good")
    weather         = models.CharField(max_length=100, blank=True)
    attendance      = models.PositiveIntegerField(null=True, blank=True)

    referee_notes   = models.TextField(blank=True, help_text="Incidents, injuries, misconduct details")
    is_abandoned    = models.BooleanField(default=False)
    abandonment_reason = models.TextField(blank=True)

    # Review
    reviewed_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="match_reports_reviewed"
    )
    reviewed_at   = models.DateTimeField(null=True, blank=True)
    reviewer_notes = models.TextField(blank=True)

    submitted_at  = models.DateTimeField(null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Match Report"
        ordering     = ["-submitted_at"]

    def __str__(self):
        return f"Report: {self.fixture}"

    def build_appointment_snapshot(self):
        from referees.models import RefereeAppointment

        appointments = RefereeAppointment.objects.filter(
            fixture_id=self.fixture_id,
        ).select_related("referee__user").order_by("role", "referee__user__last_name", "referee__user__first_name")

        return [
            {
                "role": appointment.role,
                "role_display": appointment.get_role_display(),
                "status": appointment.status,
                "referee_id": appointment.referee_id,
                "referee_name": appointment.referee.user.get_full_name(),
            }
            for appointment in appointments
        ]

    def save(self, *args, **kwargs):
        if self.fixture_id:
            self.appointment_snapshot = self.build_appointment_snapshot()
        return super().save(*args, **kwargs)

    @property
    def sport_config(self):
        return get_sport_config(self.fixture.competition.sport_type)

    @property
    def sport_family(self):
        return get_sport_family(self.fixture.competition.sport_type)


class PeriodScore(models.Model):
    """
    Per-period scores for multi-period sports.
    - Volleyball: per-set scores (e.g. Set 1: 25-23, Set 2: 22-25, ...)
    - Basketball 5×5: per-quarter scores (Q1: 22-18, Q2: 20-25, ...)
    - Basketball 3×3: single period + OT
    - Handball: per-half scores (1H: 14-12, 2H: 16-15)
    - Football: per-half scores (optional tracking)
    """
    report       = models.ForeignKey(MatchReport, on_delete=models.CASCADE, related_name="period_scores")
    period_number = models.PositiveIntegerField(help_text="1-based period number (set, quarter, half)")
    period_label  = models.CharField(max_length=30, blank=True, help_text="e.g. Set 1, Q1, 1st Half, OT1")
    home_score   = models.PositiveIntegerField(default=0)
    away_score   = models.PositiveIntegerField(default=0)
    is_overtime  = models.BooleanField(default=False, help_text="Whether this is an overtime/extra period")

    class Meta:
        ordering = ["period_number"]
        unique_together = ["report", "period_number"]

    def __str__(self):
        return f"{self.period_label}: {self.home_score}-{self.away_score}"


class MatchEvent(models.Model):
    """Goals, assists, cards, substitutions recorded in the match report."""
    # Combined event types across all sports
    EVENT_TYPES = [
        # ── Football & universal ──
        ("goal",           "Goal"),
        ("assist",         "Assist"),
        ("yellow",         "Yellow Card"),
        ("red",            "Red Card"),
        ("second_yellow",  "Second Yellow (Red)"),
        ("sub_on",         "Substitution On"),
        ("sub_off",        "Substitution Off"),
        ("injury",         "Injury"),
        ("penalty",        "Penalty Goal"),
        ("penalty_miss",   "Penalty Missed"),
        ("og",             "Own Goal"),
        # ── Volleyball ──
        ("expulsion",      "Expulsion"),
        ("timeout",        "Timeout"),
        # ── Basketball ──
        ("one_pointer",    "1-Point Shot"),
        ("two_pointer",    "2-Point Field Goal"),
        ("three_pointer",  "3-Point Field Goal"),
        ("free_throw",     "Free Throw Made"),
        ("free_throw_miss","Free Throw Missed"),
        ("foul",           "Personal Foul"),
        ("tech_foul",      "Technical Foul"),
        ("unsportsmanlike","Unsportsmanlike Foul"),
        ("disqualifying",  "Disqualifying Foul"),
        # ── Handball ──
        ("seven_m_goal",   "7m Throw Goal"),
        ("seven_m_miss",   "7m Throw Missed"),
        ("two_min",        "2-Minute Suspension"),
        ("blue_card",      "Blue Card (Report)"),
    ]
    report     = models.ForeignKey(MatchReport, on_delete=models.CASCADE, related_name="events")
    team       = models.ForeignKey("teams.Team", on_delete=models.CASCADE)
    player     = models.ForeignKey("teams.Player", on_delete=models.SET_NULL, null=True, blank=True)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    minute     = models.PositiveIntegerField(validators=[MinValueValidator(0), MaxValueValidator(200)])
    notes      = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["minute"]

    def __str__(self):
        return f"{self.event_type} @ {self.minute}' — {self.player}"


# ═══════════════════════════════════════════════════════════════════════════════
#   PLAYER STATISTICS (aggregated from match events)
# ═══════════════════════════════════════════════════════════════════════════════

class PlayerStatistics(models.Model):
    """
    Aggregated player statistics for a specific competition.
    Auto-updated when a match report is approved by the Competition Manager.
    """
    player       = models.ForeignKey("teams.Player", on_delete=models.CASCADE, related_name="statistics")
    competition  = models.ForeignKey("competitions.Competition", on_delete=models.CASCADE, related_name="player_statistics")
    team         = models.ForeignKey("teams.Team", on_delete=models.CASCADE, related_name="player_statistics")

    # Appearance stats
    matches_played   = models.PositiveIntegerField(default=0)
    matches_started  = models.PositiveIntegerField(default=0)
    matches_sub      = models.PositiveIntegerField(default=0, help_text="Appearances as substitute")
    minutes_played   = models.PositiveIntegerField(default=0)

    # Offensive stats
    goals            = models.PositiveIntegerField(default=0)
    assists          = models.PositiveIntegerField(default=0)
    penalties_scored = models.PositiveIntegerField(default=0)
    penalties_missed = models.PositiveIntegerField(default=0)
    own_goals        = models.PositiveIntegerField(default=0)

    # Disciplinary
    yellow_cards     = models.PositiveIntegerField(default=0)
    red_cards        = models.PositiveIntegerField(default=0)

    # Goalkeeper stats
    clean_sheets     = models.PositiveIntegerField(default=0, help_text="Matches where team conceded 0 goals (GK only)")
    goals_conceded   = models.PositiveIntegerField(default=0, help_text="Goals conceded while playing (GK only)")

    # Auto-calculated
    goal_contributions = models.PositiveIntegerField(default=0, help_text="Goals + Assists")

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["player", "competition"]
        ordering = ["-goals", "-assists", "-matches_played"]
        verbose_name = "Player Statistics"
        verbose_name_plural = "Player Statistics"

    def __str__(self):
        return f"{self.player.get_full_name()} — {self.competition.name} (G:{self.goals} A:{self.assists})"

    def save(self, *args, **kwargs):
        self.goal_contributions = self.goals + self.assists
        super().save(*args, **kwargs)
