"""
MKJ SUPA CUP Referees — Models
"""
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator

from accounts.models import national_id_validator


class RefereeLevel(models.TextChoices):
    FIFA     = "FIFA",     "FIFA Referee"
    CAF      = "CAF",      "CAF Referee"
    NATIONAL = "National", "FKF National"
    COUNTY   = "County",   "County Level"


class RefereeType(models.TextChoices):
    REFEREE            = "referee",            "Referee"
    ASSISTANT_REFEREE  = "assistant_referee",  "Assistant Referee"


class RefereeProfile(models.Model):
    """
    Extended profile for users with role=REFEREE.
    Created when a referee registers; activated when Referee Manager approves.
    """
    user         = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="referee_profile"
    )
    license_number = models.CharField(max_length=50, unique=True, blank=True)
    level          = models.CharField(max_length=20, choices=RefereeLevel.choices, default=RefereeLevel.COUNTY)
    county         = models.CharField(max_length=100)
    is_approved    = models.BooleanField(default=False)
    approved_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="referees_approved"
    )
    approved_at    = models.DateTimeField(null=True, blank=True)
    id_number      = models.CharField(max_length=20, blank=True, validators=[national_id_validator], help_text="National ID")
    profile_picture = models.ImageField(upload_to="referee_photos/", null=True, blank=True, help_text="Passport-size photo")
    referee_type    = models.CharField(
        max_length=20, choices=RefereeType.choices,
        default=RefereeType.REFEREE,
        help_text="Whether this official is a Referee or Assistant Referee",
    )
    discipline      = models.CharField(
        max_length=30, blank=True, default="",
        help_text="Sport discipline family e.g. football, volleyball, basketball, handball",
    )
    bio            = models.TextField(blank=True)
    years_experience = models.PositiveIntegerField(default=0)

    # Aggregated stats (updated after each match)
    total_matches  = models.PositiveIntegerField(default=0)
    avg_rating     = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)

    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Referee Profile"
        ordering     = ["user__last_name"]

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.level})"


class RefereeCertification(models.Model):
    """Certifications, licenses and badges held by a referee."""
    referee     = models.ForeignKey(RefereeProfile, on_delete=models.CASCADE, related_name="certifications")
    title       = models.CharField(max_length=200)
    issued_by   = models.CharField(max_length=200)
    issued_date = models.DateField()
    expiry_date = models.DateField(null=True, blank=True)
    certificate = models.FileField(upload_to="referee_certs/", null=True, blank=True)

    def __str__(self):
        return f"{self.title} — {self.referee}"


class AppointmentRole(models.TextChoices):
    # ── Football / Soccer (FIFA) ── Mandatory
    REFEREE    = "referee",    "Referee"
    AR1        = "ar1",        "Assistant Referee 1 (AR1)"
    AR2        = "ar2",        "Assistant Referee 2 (AR2)"
    RESERVE    = "reserve",    "Reserve Referee (RR)"
    # Football optional
    FOURTH_OFFICIAL    = "fourth_official",    "4th Official"
    MATCH_COMMISSIONER = "match_commissioner", "Match Commissioner"

    # ── Volleyball / Beach Volleyball (FIVB) ── Mandatory
    FIRST_REF    = "first_ref",    "1st Referee"
    SECOND_REF   = "second_ref",   "2nd Referee"
    SCORER       = "scorer",       "Scorer"
    LINE_JUDGE_1 = "line_judge_1", "Line Judge 1"
    LINE_JUDGE_2 = "line_judge_2", "Line Judge 2"
    # Volleyball optional
    ASSISTANT_SCORER = "assistant_scorer", "Assistant Scorer"
    LINE_JUDGE_3     = "line_judge_3",     "Line Judge 3"
    LINE_JUDGE_4     = "line_judge_4",     "Line Judge 4"

    # ── Basketball 5×5 / 3×3 (FIBA) ── Mandatory
    CREW_CHIEF   = "crew_chief",   "Crew Chief"
    UMPIRE_1     = "umpire_1",     "Umpire 1"
    UMPIRE_2     = "umpire_2",     "Umpire 2"
    COMMISSIONER = "commissioner", "Commissioner"
    # Basketball optional
    SHOT_CLOCK    = "shot_clock",    "Shot Clock Operator"
    SCORER_BBALL  = "scorer_bball",  "Scorer"

    # ── Handball / Beach Handball (IHF) ── Mandatory
    REFEREE_1    = "referee_1",    "Referee 1"
    REFEREE_2    = "referee_2",    "Referee 2"
    TIMEKEEPER   = "timekeeper",   "Timekeeper"
    SCOREKEEPER  = "scorekeeper",  "Scorekeeper"
    # Handball optional
    DELEGATE     = "delegate",     "Delegate"


# ── Sport → required official roles mapping ──
SPORT_REQUIRED_ROLES = {
    # Football
    "football_men":     ["referee", "ar1", "ar2", "reserve"],
    "football_women":   ["referee", "ar1", "ar2", "reserve"],
    # Volleyball (FIVB)
    "volleyball_men":   ["first_ref", "second_ref", "scorer", "line_judge_1", "line_judge_2"],
    "volleyball_women": ["first_ref", "second_ref", "scorer", "line_judge_1", "line_judge_2"],
    "beach_volleyball": ["first_ref", "second_ref", "scorer", "line_judge_1", "line_judge_2"],
    # Basketball 5×5 (FIBA)
    "basketball_men":   ["crew_chief", "umpire_1", "umpire_2", "commissioner"],
    "basketball_women": ["crew_chief", "umpire_1", "umpire_2", "commissioner"],
    "basketball":       ["crew_chief", "umpire_1", "umpire_2", "commissioner"],
    # Basketball 3×3 (FIBA)
    "basketball_3x3_men":   ["crew_chief", "umpire_1", "commissioner"],
    "basketball_3x3_women": ["crew_chief", "umpire_1", "commissioner"],
    "basketball_3x3":       ["crew_chief", "umpire_1", "commissioner"],
    # Handball (IHF)
    "handball_men":   ["referee_1", "referee_2", "timekeeper", "scorekeeper"],
    "handball_women": ["referee_1", "referee_2", "timekeeper", "scorekeeper"],
    "handball":       ["referee_1", "referee_2", "timekeeper", "scorekeeper"],
    "beach_handball": ["referee_1", "referee_2", "timekeeper", "scorekeeper"],
}

# ── Sport → optional official roles mapping (international standards) ──
SPORT_OPTIONAL_ROLES = {
    # Football
    "football_men":     ["fourth_official", "match_commissioner"],
    "football_women":   ["fourth_official", "match_commissioner"],
    # Volleyball (FIVB)
    "volleyball_men":   ["assistant_scorer", "line_judge_3", "line_judge_4"],
    "volleyball_women": ["assistant_scorer", "line_judge_3", "line_judge_4"],
    "beach_volleyball": ["assistant_scorer"],
    # Basketball 5×5 (FIBA)
    "basketball_men":   ["shot_clock", "scorer_bball"],
    "basketball_women": ["shot_clock", "scorer_bball"],
    "basketball":       ["shot_clock", "scorer_bball"],
    # Basketball 3×3 (FIBA)
    "basketball_3x3_men":   ["shot_clock"],
    "basketball_3x3_women": ["shot_clock"],
    "basketball_3x3":       ["shot_clock"],
    # Handball (IHF)
    "handball_men":   ["delegate"],
    "handball_women": ["delegate"],
    "handball":       ["delegate"],
    "beach_handball": ["delegate"],
}

# Head official role per sport (the official who reviews squads / files reports)
SPORT_HEAD_OFFICIAL = {
    "football_men": "referee", "football_women": "referee",
    "volleyball_men": "first_ref", "volleyball_women": "first_ref", "beach_volleyball": "first_ref",
    "basketball_men": "crew_chief", "basketball_women": "crew_chief", "basketball": "crew_chief",
    "basketball_3x3_men": "crew_chief", "basketball_3x3_women": "crew_chief", "basketball_3x3": "crew_chief",
    "handball_men": "referee_1", "handball_women": "referee_1", "handball": "referee_1", "beach_handball": "referee_1",
}

# All role keys that count as "head official" across sports
HEAD_OFFICIAL_ROLES = ["referee", "first_ref", "crew_chief", "referee_1"]

# Default fallback
_DEFAULT_ROLES = ["referee", "ar1", "ar2", "reserve"]


def get_required_roles(sport_type):
    """Return the list of required appointment role keys for a sport."""
    return SPORT_REQUIRED_ROLES.get(sport_type, _DEFAULT_ROLES)


def get_head_official_role(sport_type):
    """Return the head official role key for a sport type."""
    return SPORT_HEAD_OFFICIAL.get(sport_type, "referee")


def get_optional_roles(sport_type):
    """Return the list of optional appointment role keys for a sport."""
    return SPORT_OPTIONAL_ROLES.get(sport_type, [])


class AppointmentStatus(models.TextChoices):
    PENDING   = "pending",   "Pending Confirmation"
    CONFIRMED = "confirmed", "Confirmed"
    DECLINED  = "declined",  "Declined"
    REPLACED  = "replaced",  "Replaced"


class RefereeAppointment(models.Model):
    """Referee Manager assigns a referee to a fixture."""
    fixture   = models.ForeignKey(
        "competitions.Fixture", on_delete=models.CASCADE,
        related_name="referee_appointments"
    )
    referee   = models.ForeignKey(
        RefereeProfile, on_delete=models.CASCADE,
        related_name="appointments"
    )
    role      = models.CharField(max_length=30, choices=AppointmentRole.choices, default=AppointmentRole.REFEREE)
    status    = models.CharField(max_length=20, choices=AppointmentStatus.choices, default=AppointmentStatus.PENDING)
    appointed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="appointments_made"
    )
    appointed_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    notes        = models.TextField(blank=True)

    class Meta:
        unique_together = ["fixture", "referee", "role"]
        constraints = [
            models.UniqueConstraint(
                fields=["fixture", "role"],
                name="unique_appointment_role_per_fixture",
            ),
        ]
        ordering        = ["-appointed_at"]

    def clean(self):
        if not self.fixture or not self.role:
            return

        sport_type = getattr(getattr(self.fixture, "competition", None), "sport_type", None)
        allowed_roles = set(get_required_roles(sport_type) + get_optional_roles(sport_type))
        if sport_type and self.role not in allowed_roles:
            raise ValidationError({
                "role": f"{self.get_role_display()} is not a valid appointment role for {sport_type}."
            })

        duplicate_role = RefereeAppointment.objects.filter(
            fixture=self.fixture,
            role=self.role,
        )
        if self.pk:
            duplicate_role = duplicate_role.exclude(pk=self.pk)
        if duplicate_role.exists():
            raise ValidationError({
                "role": f"{self.get_role_display()} is already assigned for this fixture."
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.referee} → {self.fixture} ({self.role})"


class AvailabilityStatus(models.TextChoices):
    AVAILABLE   = "available",   "Available"
    UNAVAILABLE = "unavailable", "Unavailable"


class RefereeAvailability(models.Model):
    """Referee declares availability for a specific date."""
    referee = models.ForeignKey(RefereeProfile, on_delete=models.CASCADE, related_name="availability")
    date    = models.DateField()
    status  = models.CharField(max_length=20, choices=AvailabilityStatus.choices)
    notes   = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ["referee", "date"]
        ordering        = ["date"]

    def __str__(self):
        return f"{self.referee.user.get_full_name()} — {self.date} ({self.status})"


class RefereeReview(models.Model):
    """Referee Manager rates a referee after a match."""
    referee      = models.ForeignKey(RefereeProfile, on_delete=models.CASCADE, related_name="reviews")
    fixture      = models.ForeignKey(
        "competitions.Fixture", on_delete=models.CASCADE,
        related_name="referee_reviews"
    )
    reviewer     = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="referee_reviews_given"
    )
    overall_score     = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    positioning       = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    decision_making   = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    fitness           = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    communication     = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    notes             = models.TextField(blank=True)
    reviewed_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["referee", "fixture"]
        ordering = ["-reviewed_at"]

    def __str__(self):
        return f"Review: {self.referee} @ {self.fixture}"
