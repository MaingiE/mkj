"""
MKJ SUPA CUP Competitions - Core Models
"""
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone


class SportType(models.TextChoices):
    FOOTBALL_MEN       = "football_men",       "Soccer (Men)"
    FOOTBALL_WOMEN     = "football_women",     "Soccer (Women)"
    VOLLEYBALL_MEN     = "volleyball_men",     "Volleyball (Men)"
    VOLLEYBALL_WOMEN   = "volleyball_women",   "Volleyball (Women)"
    BASKETBALL_MEN     = "basketball_men",     "Basketball 5x5 (Men)"
    BASKETBALL_WOMEN   = "basketball_women",   "Basketball 5x5 (Women)"
    BASKETBALL_3X3_MEN   = "basketball_3x3_men",   "Basketball 3x3 (Men)"
    BASKETBALL_3X3_WOMEN = "basketball_3x3_women", "Basketball 3x3 (Women)"
    BASKETBALL         = "basketball",         "Basketball"
    BASKETBALL_3X3     = "basketball_3x3",     "Basketball 3x3"
    HANDBALL_MEN       = "handball_men",       "Handball (Men)"
    HANDBALL_WOMEN     = "handball_women",     "Handball (Women)"
    HANDBALL           = "handball",           "Handball"
    BEACH_VOLLEYBALL   = "beach_volleyball",   "Beach Volleyball"
    BEACH_HANDBALL     = "beach_handball",     "Beach Handball"


EXHIBITION_SPORTS = {SportType.HANDBALL_MEN, SportType.HANDBALL_WOMEN, SportType.BEACH_VOLLEYBALL, SportType.BEACH_HANDBALL}


class GenderChoice(models.TextChoices):
    MEN   = "men",   "Men"
    WOMEN = "women", "Women"
    MIXED = "mixed", "Mixed"


class CompetitionFormat(models.TextChoices):
    GROUP_STAGE       = "group_stage",       "Group Stage Only"
    KNOCKOUT          = "knockout",          "Knockout Only"
    GROUP_AND_KNOCKOUT = "group_and_knockout", "Group Stage + Knockout"


class KnockoutRound(models.TextChoices):
    ROUND_OF_32  = "round_of_32",  "Round of 32"
    ROUND_OF_16  = "round_of_16",  "Round of 16"
    QUARTERFINAL = "quarterfinal",  "Quarter-final"
    SEMIFINAL    = "semifinal",     "Semi-final"
    THIRD_PLACE  = "third_place",   "3rd Place Play-off"
    FINAL        = "final",         "Final"


class CompetitionStatus(models.TextChoices):
    UPCOMING     = "upcoming",     "Upcoming"
    GROUP_STAGE  = "group_stage",  "Group Stage"
    KNOCKOUT     = "knockout",     "Knockout Stage"
    ACTIVE       = "active",       "Active / Ongoing"
    COMPLETED    = "completed",    "Completed"
    CANCELLED    = "cancelled",    "Cancelled"


class AgeGroup(models.TextChoices):
    U13 = "U13", "Under 13"
    U15 = "U15", "Under 15"
    U17 = "U17", "Under 17"
    U20 = "U20", "Under 20"
    U23 = "U23", "Under 23"
    OPEN = "Open", "Open Age"


class Competition(models.Model):
    name        = models.CharField(max_length=200, unique=True)
    sport_type  = models.CharField(
        max_length=30, choices=SportType.choices, default=SportType.FOOTBALL_MEN,
        help_text="Sport discipline for this competition"
    )
    gender      = models.CharField(
        max_length=10, choices=GenderChoice.choices, default=GenderChoice.MEN,
        help_text="Gender category for this competition"
    )
    format_type = models.CharField(
        max_length=30, choices=CompetitionFormat.choices,
        default=CompetitionFormat.GROUP_AND_KNOCKOUT,
        help_text="Competition format: group stage, knockout, or both"
    )
    is_exhibition = models.BooleanField(
        default=False,
        help_text="Mark as exhibition match (e.g. Beach Volleyball, Beach Handball)"
    )
    season      = models.CharField(max_length=10, default="2025")
    age_group   = models.CharField(max_length=10, choices=AgeGroup.choices, default=AgeGroup.U17)
    status      = models.CharField(max_length=20, choices=CompetitionStatus.choices, default=CompetitionStatus.UPCOMING)
    description = models.TextField(blank=True)
    rules       = models.TextField(blank=True, help_text="Competition rules, regulations, and format details")
    start_date  = models.DateField()
    end_date    = models.DateField()
    max_teams   = models.PositiveIntegerField(default=16)
    teams_per_group = models.PositiveIntegerField(
        default=4, help_text="Number of teams per group in group stage"
    )
    qualify_from_group = models.PositiveIntegerField(
        default=2, help_text="Number of teams that qualify from each group to knockout"
    )
    created_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="competitions_created"
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]
        verbose_name = "Competition"
        verbose_name_plural = "Competitions"

    def __str__(self):
        return f"{self.name} ({self.season})"

    @property
    def has_group_stage(self):
        return self.format_type in (CompetitionFormat.GROUP_STAGE, CompetitionFormat.GROUP_AND_KNOCKOUT)

    @property
    def has_knockout(self):
        return self.format_type in (CompetitionFormat.KNOCKOUT, CompetitionFormat.GROUP_AND_KNOCKOUT)

    def save(self, *args, **kwargs):
        # Auto-mark beach sports as exhibition
        if self.sport_type in EXHIBITION_SPORTS:
            self.is_exhibition = True
        # Auto-set gender from sport type if football
        if self.sport_type == SportType.FOOTBALL_WOMEN:
            self.gender = GenderChoice.WOMEN
        elif self.sport_type == SportType.FOOTBALL_MEN:
            self.gender = GenderChoice.MEN
        super().save(*args, **kwargs)


class Venue(models.Model):
    name       = models.CharField(max_length=200)
    county     = models.CharField(max_length=100)
    city       = models.CharField(max_length=100)
    address    = models.TextField(blank=True)
    capacity   = models.PositiveIntegerField(default=0)
    surface    = models.CharField(max_length=100, default="Natural Grass")
    facilities = models.TextField(blank=True, help_text="List facilities available")
    photo      = models.ImageField(upload_to="venues/", null=True, blank=True)
    is_active  = models.BooleanField(default=True)
    latitude   = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude  = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name}, {self.county}"


class Pool(models.Model):
    """A group/pool within a competition (e.g., Group A, Group B)."""
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name="pools")
    name        = models.CharField(max_length=50, help_text="e.g., Group A, Group B, Pool 1")
    venue       = models.ForeignKey(Venue, on_delete=models.SET_NULL, null=True, blank=True,
                                    help_text="Default venue for fixtures in this pool")
    notes       = models.TextField(blank=True)

    class Meta:
        unique_together = ["competition", "name"]
        ordering = ["competition", "name"]

    def __str__(self):
        return f"{self.competition.name} - {self.name}"


class PoolTeam(models.Model):
    """Team assignment to a pool with standing data."""
    pool       = models.ForeignKey(Pool, on_delete=models.CASCADE, related_name="pool_teams")
    team       = models.ForeignKey("teams.Team", on_delete=models.CASCADE, related_name="pool_memberships")
    played     = models.PositiveIntegerField(default=0)
    won        = models.PositiveIntegerField(default=0)
    drawn      = models.PositiveIntegerField(default=0)
    lost       = models.PositiveIntegerField(default=0)
    goals_for  = models.PositiveIntegerField(default=0)
    goals_against = models.PositiveIntegerField(default=0)

    # Sport-specific stats (volleyball sets, basketball quarters etc.)
    sets_won      = models.PositiveIntegerField(default=0, help_text="For volleyball: sets won")
    sets_lost     = models.PositiveIntegerField(default=0, help_text="For volleyball: sets lost")
    bonus_points  = models.IntegerField(default=0, help_text="Bonus/penalty points (e.g. deductions)")

    class Meta:
        unique_together = ["pool", "team"]
        ordering = ["-won", "-goals_for"]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.team_id:
            if self.team.status != "registered":
                raise ValidationError(
                    f"{self.team.name} is not approved. Only registered teams can be pooled."
                )

    @property
    def points(self):
        """
        Sport-specific points calculation.
        - Football: W×3 + D×1
        - Volleyball: bonus_points (FIVB system: 3/2/1/0 based on set score)
        - Basketball: bonus_points (FIBA: W=2, L=1)
        - Handball: W×2 + D×1
        """
        sport = self.pool.competition.sport_type if self.pool and self.pool.competition else None
        if sport:
            from matches.models import get_sport_family
            family = get_sport_family(sport)
            if family in ("volleyball", "basketball_5x5", "basketball_3x3"):
                return self.bonus_points
            elif family == "handball":
                return (self.won * 2) + self.drawn + self.bonus_points
        return (self.won * 3) + self.drawn + self.bonus_points

    @property
    def goal_difference(self):
        return self.goals_for - self.goals_against

    @property
    def set_difference(self):
        return self.sets_won - self.sets_lost

    @property
    def sport_family(self):
        if self.pool and self.pool.competition:
            from matches.models import get_sport_family
            return get_sport_family(self.pool.competition.sport_type)
        return "football"

    def __str__(self):
        return f"{self.team.name} in {self.pool}"


class FixtureStatus(models.TextChoices):
    PENDING       = "pending",    "Pending"
    CONFIRMED     = "confirmed",  "Confirmed"
    LIVE          = "live",       "Live"
    COMPLETED     = "completed",  "Completed"
    POSTPONED     = "postponed",  "Postponed"
    CANCELLED     = "cancelled",  "Cancelled"


class Fixture(models.Model):
    """A scheduled match between two teams."""
    competition    = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name="fixtures")
    pool           = models.ForeignKey(Pool, on_delete=models.SET_NULL, null=True, blank=True, related_name="fixtures")
    home_team      = models.ForeignKey("teams.Team", on_delete=models.CASCADE, related_name="home_fixtures")
    away_team      = models.ForeignKey("teams.Team", on_delete=models.CASCADE, related_name="away_fixtures")
    venue          = models.ForeignKey(Venue, on_delete=models.SET_NULL, null=True, blank=True)
    match_date     = models.DateField()
    kickoff_time   = models.TimeField()
    status         = models.CharField(max_length=20, choices=FixtureStatus.choices, default=FixtureStatus.PENDING)
    round_number   = models.PositiveIntegerField(null=True, blank=True)

    # ── Knockout stage fields ──────────────────────────────────────────────
    is_knockout      = models.BooleanField(default=False, help_text="Knockout/elimination match")
    knockout_round   = models.CharField(
        max_length=20, choices=KnockoutRound.choices, blank=True, default="",
        help_text="Applicable knockout round (R16, QF, SF, Final)"
    )
    bracket_position = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Position in bracket (1=first match of this round)"
    )
    leg_number       = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Leg number for two-legged ties (1 or 2)"
    )

    # Results (filled after match)
    home_score     = models.PositiveIntegerField(null=True, blank=True)
    away_score     = models.PositiveIntegerField(null=True, blank=True)
    is_walkover    = models.BooleanField(default=False)
    walkover_team  = models.ForeignKey(
        "teams.Team", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="walkovers_won"
    )
    # Extra time & penalties (knockout matches)
    home_score_et  = models.PositiveIntegerField(null=True, blank=True, help_text="Home score after extra time")
    away_score_et  = models.PositiveIntegerField(null=True, blank=True, help_text="Away score after extra time")
    home_penalties = models.PositiveIntegerField(null=True, blank=True, help_text="Home penalty shootout score")
    away_penalties = models.PositiveIntegerField(null=True, blank=True, help_text="Away penalty shootout score")
    winner         = models.ForeignKey(
        "teams.Team", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="fixtures_won", help_text="Winner (auto-set or set for knockout ties)"
    )

    created_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="fixtures_created"
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["match_date", "kickoff_time"]

    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}
        for side, fk in [("home_team", self.home_team_id), ("away_team", self.away_team_id)]:
            if fk:
                team = getattr(self, side)
                if team.status != "registered":
                    errors[side] = f"{team.name} is not an approved team."
        if errors:
            raise ValidationError(errors)

    def determine_winner(self):
        """Determine and set the winner based on scores (used for knockout matches)."""
        if self.home_score is None or self.away_score is None:
            return None
        if self.home_score > self.away_score:
            self.winner = self.home_team
        elif self.away_score > self.home_score:
            self.winner = self.away_team
        elif self.home_penalties is not None and self.away_penalties is not None:
            if self.home_penalties > self.away_penalties:
                self.winner = self.home_team
            elif self.away_penalties > self.home_penalties:
                self.winner = self.away_team
        elif self.home_score_et is not None and self.away_score_et is not None:
            if self.home_score_et > self.away_score_et:
                self.winner = self.home_team
            elif self.away_score_et > self.home_score_et:
                self.winner = self.away_team
        return self.winner

    def __str__(self):
        label = f"{self.home_team} vs {self.away_team} - {self.match_date}"
        if self.is_knockout and self.knockout_round:
            label = f"[{self.get_knockout_round_display()}] {label}"
        return label

    @property
    def kickoff_datetime(self):
        from datetime import datetime
        return datetime.combine(self.match_date, self.kickoff_time)

    @property
    def squad_deadline(self):
        """Squad must be submitted SQUAD_SUBMISSION_HOURS_BEFORE_KICKOFF hours before KO."""
        from django.conf import settings as conf
        hours = getattr(conf, "SQUAD_SUBMISSION_HOURS_BEFORE_KICKOFF", 4)
        from datetime import timedelta
        import pytz
        nairobi = pytz.timezone("Africa/Nairobi")
        ko = nairobi.localize(self.kickoff_datetime)
        return ko - timedelta(hours=hours)


