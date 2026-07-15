"""
MKJ SUPA CUP Teams - Models
"""
import re

from django.db import models
from django.db.models import Q
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify

from competitions.models import Competition, SportType
from accounts.models import KenyaCounty, MakueniSubCounty, kenya_phone_validator, national_id_validator


# ══════════════════════════════════════════════════════════════════════════════
#  SQUAD SIZE LIMITS  (per discipline)
# ══════════════════════════════════════════════════════════════════════════════
SQUAD_LIMITS = {
    SportType.FOOTBALL_MEN:       24,
    SportType.FOOTBALL_WOMEN:     24,
    SportType.VOLLEYBALL_MEN:     14,
    SportType.VOLLEYBALL_WOMEN:   14,
    SportType.HANDBALL_MEN:       14,
    SportType.HANDBALL_WOMEN:     14,
    SportType.BASKETBALL_MEN:     12,
    SportType.BASKETBALL_WOMEN:   12,
    SportType.BASKETBALL_3X3_MEN: 8,
    SportType.BASKETBALL_3X3_WOMEN: 8,
}


# ══════════════════════════════════════════════════════════════════════════════
#  COUNTY REGISTRATION  (County Sports Admin workflow)
# ══════════════════════════════════════════════════════════════════════════════

class CountyRegStatus(models.TextChoices):
    PENDING_PAYMENT   = "pending_payment",   "Pending Payment"
    PAYMENT_SUBMITTED = "payment_submitted", "Payment Submitted"
    APPROVED          = "approved",          "Approved"
    REJECTED          = "rejected",          "Rejected"


class CountyRegistration(models.Model):
    """
    One-per-county registration.  The county sports admin creates this at
    sign-up; a treasurer later approves payment.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="county_registration",
    )
    county = models.CharField(
        max_length=100,
        choices=KenyaCounty.choices,
        unique=True,
        help_text="Kenyan county (only one admin per county)",
    )

    # Director of Sports - county contact person
    director_name = models.CharField(
        max_length=200, blank=True, default="",
        help_text="Full name of the Director of Sports for this county",
    )
    director_phone = models.CharField(
        max_length=13, validators=[kenya_phone_validator],
        help_text="Phone number of the Director of Sports",
    )

    status = models.CharField(
        max_length=20,
        choices=CountyRegStatus.choices,
        default=CountyRegStatus.PENDING_PAYMENT,
    )
    
    level = models.CharField(
        max_length=20,
        default="county",
        help_text="Competition level: ward, subcounty, or county",
    )

    # Payment evidence
    mpesa_reference = models.CharField(max_length=100, blank=True, default="",
                                        help_text="M-Pesa transaction code from confirmation SMS")
    mpesa_phone = models.CharField(max_length=13, blank=True, default="", validators=[kenya_phone_validator],
                                    help_text="Phone number used for M-Pesa payment")
    mpesa_checkout_id = models.CharField(max_length=100, blank=True, default="",
                                          help_text="Daraja STK push CheckoutRequestID")
    bank_slip = models.FileField(upload_to="county_reg/bank_slips/", null=True, blank=True,
                                  help_text="Bank deposit slip (image or PDF)")
    bank_reference = models.CharField(max_length=100, blank=True, default="",
                                       help_text="Bank payment/transfer reference code")
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payment_method = models.CharField(max_length=20, blank=True, default="",
                                       help_text="mpesa or bank_transfer")
    payment_submitted_at = models.DateTimeField(null=True, blank=True)

    # Approval
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="county_approvals",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["county"]

    def __str__(self):
        return f"{self.county} - {self.get_status_display()}"

    @property
    def is_approved(self):
        return self.status == CountyRegStatus.APPROVED


class CountyDiscipline(models.Model):
    """
    A discipline (sport) that a county has opted to participate in.
    Created only after the county registration is approved.
    """
    registration = models.ForeignKey(
        CountyRegistration, on_delete=models.CASCADE,
        related_name="disciplines",
    )
    sport_type = models.CharField(max_length=30, choices=SportType.choices)
    sub_county = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Sub-county or constituency that owns this discipline entry",
    )
    level = models.CharField(
        max_length=20,
        default="county",
        help_text="Competition level: ward, subcounty, or county",
    )
    ward = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Ward for ward-level competitions",
    )

    class Meta:
        unique_together = ["registration", "sport_type", "sub_county", "level", "ward"]
        ordering = ["sub_county", "sport_type"]

    def __str__(self):
        owner = self.sub_county or self.registration.county
        return f"{owner} - {self.get_sport_type_display()}"

    @property
    def squad_limit(self):
        return SQUAD_LIMITS.get(self.sport_type, 30)

    @property
    def player_count(self):
        return self.players.count()

    @property
    def can_add_player(self):
        return self.player_count < self.squad_limit

    def generated_team_name(self):
        base_name = f"{self.sub_county or self.registration.county} {self.get_sport_type_display()}"
        base_name = re.sub(r"\s+", " ", base_name).strip()
        candidate = base_name[:200]
        suffix = 1
        while Team.objects.filter(name=candidate).exclude(source_discipline=self).exists():
            token = f" #{suffix}"
            candidate = f"{base_name[:200 - len(token)]}{token}"
            suffix += 1
        return candidate

    def _default_mkj_competition(self):
        mkj_qs = Competition.objects.filter(
            Q(name__icontains="mkj")
            & Q(name__icontains="supa")
            & Q(name__icontains="cup"),
            sport_type=self.sport_type,
        )

        for status in ("active", "group_stage", "knockout", "upcoming"):
            comp = mkj_qs.filter(status=status).order_by("-start_date").first()
            if comp:
                return comp

        return mkj_qs.order_by("-start_date").first()

    def ensure_linked_team(self):
        county_obj = get_or_create_county_record(
            self.registration.county,
            sports_officer_name=self.registration.director_name,
            sports_officer_email=getattr(self.registration.user, "email", ""),
            sports_officer_phone=self.registration.director_phone,
        )
        default_competition = self._default_mkj_competition()
        defaults = {
            "name": self.generated_team_name(),
            "county": county_obj,
            "sub_county": self.sub_county,
            "sport_type": self.sport_type,
            "competition": default_competition,
            "status": TeamStatus.REGISTERED,
            "payment_confirmed": True,
            "payment_amount": 0,
            "payment_confirmed_at": timezone.now(),
            "contact_phone": self.registration.director_phone or getattr(self.registration.user, "phone", "+254700000000"),
            "contact_email": getattr(self.registration.user, "email", ""),
        }
        team, created = Team.objects.get_or_create(source_discipline=self, defaults=defaults)
        if not created:
            team.name = self.generated_team_name()
            team.county = county_obj
            team.sub_county = self.sub_county
            team.sport_type = self.sport_type
            if default_competition:
                team.competition = default_competition
            team.status = TeamStatus.REGISTERED
            team.payment_confirmed = True
            if not team.payment_confirmed_at:
                team.payment_confirmed_at = timezone.now()
            if not team.contact_phone:
                team.contact_phone = defaults["contact_phone"]
            if not team.contact_email:
                team.contact_email = defaults["contact_email"]
            team.save(update_fields=[
                "name", "county", "sub_county", "sport_type", "competition", "status",
                "payment_confirmed", "payment_confirmed_at", "contact_phone", "contact_email",
            ])
        return team

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.ensure_linked_team()


class CountyPlayer(models.Model):
    """
    A player registered under a county discipline.
    A player (by national_id) can only belong to one discipline and one county.
    """
    discipline = models.ForeignKey(
        CountyDiscipline, on_delete=models.CASCADE,
        related_name="players",
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField(null=True, blank=True)
    age_value = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Player age (used when DOB is not available)",
    )
    national_id_number = models.CharField(
        max_length=20, unique=True, validators=[national_id_validator],
        help_text="National ID - unique across all counties and disciplines",
    )
    registration_code = models.CharField(
        max_length=20, blank=True, default="",
        unique=True,
        help_text="System-generated unique registration code (auto-assigned on save for ward players)",
        db_index=True,
    )
    huduma_number = models.CharField(
        max_length=30, blank=True, default="",
        help_text="Huduma Namba / Huduma Kenya number",
    )
    phone = models.CharField(max_length=13, validators=[kenya_phone_validator])
    sub_county = models.CharField(
        max_length=100, blank=True, default="",
        help_text="Sub-county the player represents",
    )
    ward = models.CharField(
        max_length=100, blank=True, default="",
        help_text="Ward within the sub-county",
    )
    position = models.CharField(max_length=10, blank=True, default="",
                                help_text="Player position (where applicable)")
    jersey_number = models.PositiveIntegerField(null=True, blank=True,
                                                help_text="Jersey number")
    ligi_mashinani_team = models.CharField(
        max_length=200, blank=True, default="",
        help_text="Team in Ligi Mashinani",
    )
    
    # ── Player promotion tracking (ward → sub-county → county) ────────────────
    source_ward_player = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="subcounty_instances",
        help_text="Ward player this sub-county player was promoted from",
    )
    source_subcounty_player = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="county_instances",
        help_text="Sub-county player this county player was promoted from",
    )
    
    photo = models.ImageField(upload_to="county_players/photos/", null=True, blank=True,
                              help_text="Passport-size photo (required)")
    iprs_photo = models.ImageField(
        upload_to="county_players/iprs_photos/", null=True, blank=True,
        help_text="Passport photo returned from IPRS lookup (auto-populated)",
    )
    id_document = models.ImageField(upload_to="county_players/ids/", null=True, blank=True,
                                    help_text="Copy of National ID (required)")
    birth_certificate = models.ImageField(
        upload_to="county_players/birth_certs/", null=True, blank=True,
        help_text="Copy of Birth Certificate (optional)",
    )

    # ══════════════════════════════════════════════════════════════════════
    #  4-STEP SEQUENTIAL VERIFICATION WORKFLOW
    #  Step 1: Document Verification  →  Step 2: Huduma Check
    #  Step 3: Higher Leagues Check   →  Step 4: IPRS Age Verification
    #  Each step must pass before the next one unlocks.
    # ══════════════════════════════════════════════════════════════════════

    # ── Overall status (auto-computed from the 4 steps) ───────────────────
    verification_status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending Verification"),
            ("verified", "Verified / Approved"),
            ("rejected", "Rejected"),
            ("resubmit", "Requires Resubmission"),
        ],
        default="pending",
    )
    rejection_reason = models.TextField(blank=True, default="")

    # ── Step 1: Document Verification ─────────────────────────────────────
    doc_status = models.CharField(
        max_length=20,
        choices=[
            ("not_checked", "Not Checked"),
            ("verified", "Verified"),
            ("rejected", "Rejected"),
        ],
        default="not_checked",
        help_text="Step 1 - manual review of photo, ID document & birth certificate",
    )
    doc_verified_at = models.DateTimeField(null=True, blank=True)
    doc_rejection_reason = models.TextField(blank=True, default="")

    # ── Step 2: Huduma Kenya Check ────────────────────────────────────────
    huduma_status = models.CharField(
        max_length=20,
        choices=[
            ("not_checked", "Not Checked"),
            ("verified", "Verified"),
            ("failed", "Failed"),
        ],
        default="not_checked",
    )
    huduma_verified_at = models.DateTimeField(null=True, blank=True)
    huduma_notes = models.TextField(blank=True, default="")

    # ── Step 3: Higher League / National Team Check ───────────────────────
    higher_league_status = models.CharField(
        max_length=20,
        choices=[
            ("not_checked", "Not Checked"),
            ("clear", "Clear"),
            ("flagged", "Flagged - Higher League / National Team"),
        ],
        default="not_checked",
        help_text="Check if player is registered in a higher league or national team",
    )
    higher_league_details = models.TextField(
        blank=True, default="",
        help_text="Details of higher league / national team participation if flagged",
    )
    higher_league_checked_at = models.DateTimeField(null=True, blank=True)

    # ── Step 4: IPRS Age Verification (manual now, auto when API ready) ──
    iprs_age_status = models.CharField(
        max_length=20,
        choices=[
            ("not_checked", "Not Checked"),
            ("verified", "Age Verified"),
            ("failed", "Age Mismatch / Failed"),
        ],
        default="not_checked",
        help_text="Step 4 - verify age via IPRS (manual now, automated when API available)",
    )
    iprs_age_verified_at = models.DateTimeField(null=True, blank=True)
    iprs_age_notes = models.TextField(blank=True, default="")

    # ── Director of Sports Final Approval ─────────────────────────────────
    director_approved = models.BooleanField(
        default=False,
        help_text="Final approval by Director of Sports",
    )
    director_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="director_approved_players",
    )
    director_approved_at = models.DateTimeField(null=True, blank=True)
    director_disapproved = models.BooleanField(
        default=False,
        help_text="Disapproved by Director of Sports",
    )
    director_disapproval_reason = models.TextField(
        blank=True, default="",
        help_text="Reason for disapproval",
    )
    director_locked = models.BooleanField(
        default=False,
        help_text="Locked by Director of Sports - no further edits except by Director",
    )
    director_locked_at = models.DateTimeField(null=True, blank=True)

    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.discipline})"

    @property
    def age(self):
        if self.date_of_birth:
            from django.utils import timezone
            today = timezone.now().date()
            dob = self.date_of_birth
            return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        return self.age_value

    @property
    def is_verified(self):
        """True only when ALL 3 verification steps have passed."""
        return (
            self.doc_status == "verified"
            and self.iprs_age_status == "verified"
            and self.higher_league_status == "clear"
        )

    @property
    def current_verification_step(self):
        """Return the step number the player is currently on (1-3), or 4 if done."""
        if self.doc_status != "verified":
            return 1
        if self.iprs_age_status != "verified":
            return 2
        if self.higher_league_status != "clear":
            return 3
        return 4  # Fully verified

    @property
    def step_label(self):
        labels = {1: "Documents", 2: "Age Verification", 3: "Higher Leagues", 4: "Complete"}
        return labels.get(self.current_verification_step, "")

    def update_overall_status(self):
        """Recompute verification_status from the 3 step statuses."""
        if self.is_verified:
            self.verification_status = "verified"
            self.rejection_reason = ""
        elif (
            self.doc_status == "rejected"
            or self.iprs_age_status == "failed"
            or self.higher_league_status == "flagged"
        ):
            self.verification_status = "rejected"
        else:
            self.verification_status = "pending"

    @property
    def is_football(self):
        return self.discipline.sport_type in (
            SportType.FOOTBALL_MEN, SportType.FOOTBALL_WOMEN
        )

    @property
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    def _generate_registration_code(self):
        """
        Auto-generate a unique ward-level registration code.
        Format: LM-{WARD_ABBREV}-{SPORT_ABBREV}-{6-DIGIT-SEQUENCE}
        e.g. LM-MKA-FM-000012
        Only generated for ward-level (level='ward') CountyPlayer records.
        """
        discipline = self.discipline
        ward_abbrev = (discipline.ward or 'WRD')[:3].upper()
        sport_map = {
            'football_men': 'FM', 'football_women': 'FW',
            'volleyball_men': 'VM', 'volleyball_women': 'VW',
            'basketball_men': 'BM', 'basketball_women': 'BW',
            'basketball_3x3_men': 'B3M', 'basketball_3x3_women': 'B3W',
            'handball_men': 'HM', 'handball_women': 'HW',
        }
        sport_abbrev = sport_map.get(discipline.sport_type, 'XX')
        prefix = f"LM-{ward_abbrev}-{sport_abbrev}-"
        existing_codes = CountyPlayer.objects.filter(
            registration_code__startswith=prefix
        ).values_list('registration_code', flat=True)
        used_nums = set()
        for code in existing_codes:
            try:
                used_nums.add(int(code.replace(prefix, '')))
            except ValueError:
                pass
        seq = 1
        while seq in used_nums:
            seq += 1
        return f"{prefix}{seq:06d}"

    def save(self, *args, **kwargs):
        # Auto-generate registration code for ward-level players on first save
        if not self.registration_code and self.discipline_id:
            try:
                disc = self.discipline if hasattr(self, '_discipline_cache') else \
                    CountyDiscipline.objects.filter(pk=self.discipline_id).first()
                if disc and disc.level == 'ward':
                    self.registration_code = self._generate_registration_code()
            except Exception:
                pass
        super().save(*args, **kwargs)

class WardLonglistStatus(models.TextChoices):
    DRAFT          = "draft",          "Draft"
    SUBMITTED      = "submitted",      "Submitted for Review"
    WSCC_APPROVED  = "wscc_approved",  "WSCC Approved"
    RETURNED       = "returned",       "Returned for Corrections"


class WardLonglist(models.Model):
    """
    Ward-level player longlist for Ligi Mashinani competitions.
    Created when a ward team manager is approved and linked to a ward discipline.
    """
    discipline = models.OneToOneField(
        CountyDiscipline,
        on_delete=models.CASCADE,
        related_name="ward_longlist",
        limit_choices_to={"level": "ward"},
        help_text="Ward discipline this longlist belongs to",
    )
    status = models.CharField(
        max_length=20,
        choices=WardLonglistStatus.choices,
        default=WardLonglistStatus.DRAFT,
        help_text="Current status in the WSCC approval workflow",
    )
    submitted_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the longlist was submitted for WSCC review",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="ward_longlists_reviewed",
        help_text="WSCC who reviewed this longlist",
    )
    reviewed_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the WSCC reviewed this longlist",
    )
    return_reason = models.TextField(
        blank=True, default="",
        help_text="Reason provided by WSCC when returning longlist for corrections",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Ward Longlist"
        verbose_name_plural = "Ward Longlists"

    def __str__(self):
        return f"{self.discipline} Longlist - {self.get_status_display()}"

    @property
    def is_locked(self):
        """True when longlist cannot be edited (submitted or approved)."""
        return self.status in (WardLonglistStatus.SUBMITTED, WardLonglistStatus.WSCC_APPROVED)

    @property
    def can_submit(self):
        """True when longlist can be submitted (has players and is in draft/returned status)."""
        return self.status in (WardLonglistStatus.DRAFT, WardLonglistStatus.RETURNED) and self.discipline.player_count > 0


# ══════════════════════════════════════════════════════════════════════════════
#  TECHNICAL BENCH MEMBER (per discipline per county)
# ══════════════════════════════════════════════════════════════════════════════

class TechnicalBenchRole(models.TextChoices):
    TEAM_MANAGER    = "team_manager",    "Team Manager"
    HEAD_COACH      = "head_coach",      "Head Coach"
    ASSISTANT_COACH = "assistant_coach", "Assistant Coach"


class TechnicalBenchMember(models.Model):
    """
    A delegation / technical bench member for a county discipline.
    Each discipline requires: Team Manager, Head Coach, Assistant Coach.
    The Team Manager gets a dedicated portal with match-day squad selection capabilities.
    """
    discipline = models.ForeignKey(
        CountyDiscipline, on_delete=models.CASCADE,
        related_name="technical_bench",
    )
    role = models.CharField(max_length=20, choices=TechnicalBenchRole.choices)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=13, validators=[kenya_phone_validator])
    national_id_number = models.CharField(max_length=20, blank=True, default="", validators=[national_id_validator])
    photo = models.ImageField(upload_to="technical_bench/photos/", null=True, blank=True)
    id_document = models.ImageField(upload_to="technical_bench/ids/", null=True, blank=True)

    # Link to user account (created when Team Manager is added)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="technical_bench_profile",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["discipline", "role"]
        ordering = ["discipline", "role"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.get_role_display()} ({self.discipline})"

    @property
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"


# ══════════════════════════════════════════════════════════════════════════════
#  COUNTY DELEGATION MEMBERS (county-wide officials accompanying delegation)
# ══════════════════════════════════════════════════════════════════════════════

class CountyDelegationRole(models.TextChoices):
    CECM_SPORTS = "cecm_sports", "CECM - Sports"
    CHIEF_OFFICER_SPORTS = "chief_officer_sports", "Chief Officer - Sports"
    COUNTY_SECRETARY = "county_secretary", "County Secretary"
    COUNTY_ATTORNEY = "county_attorney", "County Attorney"
    COUNTY_PROTOCOL = "county_protocol", "County Protocol Officer"
    COUNTY_LIAISON = "county_liaison", "County Liaison Officer"
    COUNTY_MEDIA = "county_media", "County Media Officer"
    COUNTY_MEDICAL = "county_medical", "County Medical Officer"
    OTHER = "other", "Other"


class CountyDelegationMember(models.Model):
    """County-level delegation officials not tied to a specific discipline."""
    registration = models.ForeignKey(
        CountyRegistration, on_delete=models.CASCADE,
        related_name="delegation_members",
    )
    role = models.CharField(max_length=40, choices=CountyDelegationRole.choices)
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=13, validators=[kenya_phone_validator])
    national_id_number = models.CharField(max_length=20, validators=[national_id_validator])
    email = models.EmailField(blank=True, default="")

    # Optional linked user account (mandatory for CECM role)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="county_delegation_profile",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["registration", "role", "full_name"]
        unique_together = ["registration", "national_id_number"]

    def __str__(self):
        return f"{self.full_name} - {self.get_role_display()} ({self.registration.county})"

    @property
    def is_cecm(self):
        return self.role == CountyDelegationRole.CECM_SPORTS


# ══════════════════════════════════════════════════════════════════════════════
#  COUNTY MODEL
# ══════════════════════════════════════════════════════════════════════════════

class County(models.Model):
    """Kenyan counties with sports officer contact information."""
    name = models.CharField(max_length=100, unique=True, help_text="County name (e.g., Nairobi, Mombasa)")
    code = models.CharField(max_length=10, unique=True, help_text="County code (e.g., NAI, MSA)")
    capital = models.CharField(max_length=100, blank=True, help_text="County capital/headquarters")
    
    # Sports officer contact details
    sports_officer_name = models.CharField(max_length=200, blank=True, help_text="Sports officer full name")
    sports_officer_email = models.EmailField(blank=True, help_text="Sports officer email address")
    sports_officer_phone = models.CharField(max_length=13, blank=True, validators=[kenya_phone_validator], help_text="Sports officer phone number")
    
    # Alternative contact (backup)
    alt_contact_name = models.CharField(max_length=200, blank=True, help_text="Alternative contact name")
    alt_contact_email = models.EmailField(blank=True, help_text="Alternative contact email")
    alt_contact_phone = models.CharField(max_length=13, blank=True, validators=[kenya_phone_validator], help_text="Alternative contact phone")
    
    office_address = models.TextField(blank=True, help_text="County sports office address")
    is_active = models.BooleanField(default=True, help_text="County is active and participating")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Counties'
    
    def __str__(self):
        return self.name
    
    @property
    def primary_contact_email(self):
        """Return sports officer email, fallback to alternative contact email."""
        return self.sports_officer_email or self.alt_contact_email
    
    @property
    def primary_contact_name(self):
        """Return sports officer name, fallback to alternative contact name."""
        return self.sports_officer_name or self.alt_contact_name


def _county_code_base(county_name):
    base = slugify(county_name or "county").replace("-", "").upper()
    return (base or "COUNTY")[:10]


def get_or_create_county_record(county_name, sports_officer_name="", sports_officer_email="", sports_officer_phone=""):
    county = County.objects.filter(name__iexact=county_name).first()
    if county:
        updated = False
        if sports_officer_name and not county.sports_officer_name:
            county.sports_officer_name = sports_officer_name
            updated = True
        if sports_officer_email and not county.sports_officer_email:
            county.sports_officer_email = sports_officer_email
            updated = True
        if sports_officer_phone and not county.sports_officer_phone:
            county.sports_officer_phone = sports_officer_phone
            updated = True
        if updated:
            county.save(update_fields=["sports_officer_name", "sports_officer_email", "sports_officer_phone", "updated_at"])
        return county

    code_base = _county_code_base(county_name)
    code = code_base
    suffix = 1
    while County.objects.filter(code=code).exists():
        token = str(suffix)
        code = f"{code_base[:10 - len(token)]}{token}"
        suffix += 1

    return County.objects.create(
        name=county_name,
        code=code,
        sports_officer_name=sports_officer_name,
        sports_officer_email=sports_officer_email,
        sports_officer_phone=sports_officer_phone,
    )


class TeamStatus(models.TextChoices):
    PENDING    = "pending",    "Pending Approval"
    REGISTERED = "registered", "Registered"
    SUSPENDED  = "suspended",  "Suspended"


class Team(models.Model):
    name        = models.CharField(max_length=200, unique=True)
    county      = models.ForeignKey(County, on_delete=models.CASCADE, related_name="teams", help_text="County this team represents")
    sub_county  = models.CharField(max_length=100, blank=True, default="", help_text="Sub-county or constituency this team represents")
    sport_type  = models.CharField(
        max_length=30, choices=SportType.choices, default=SportType.FOOTBALL_MEN,
        help_text="Sport this team competes in"
    )
    source_discipline = models.OneToOneField(
        "CountyDiscipline",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linked_team",
    )
    competition = models.ForeignKey(
        "competitions.Competition", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="teams"
    )
    manager     = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="managed_teams"
    )
    status      = models.CharField(max_length=20, choices=TeamStatus.choices, default=TeamStatus.PENDING)
    badge       = models.ImageField(upload_to="team_badges/", null=True, blank=True)
    county_logo = models.ImageField(upload_to="county_logos/", null=True, blank=True, help_text="County government logo")

    # ── Kit details (mandatory for registration) ───────────────────────────
    # Home kit
    home_outfield_colour = models.CharField(max_length=50, blank=True, help_text="Home outfield jersey colour")
    home_shorts_colour   = models.CharField(max_length=50, blank=True, help_text="Home shorts colour")
    home_socks_colour    = models.CharField(max_length=50, blank=True, help_text="Home socks colour")
    home_gk_colour       = models.CharField(max_length=50, blank=True, help_text="Home goalkeeper jersey colour")
    home_kit_image       = models.ImageField(upload_to="kits/home/", null=True, blank=True, help_text="Photo of home kit")

    # Away kit
    away_outfield_colour = models.CharField(max_length=50, blank=True, help_text="Away outfield jersey colour")
    away_shorts_colour   = models.CharField(max_length=50, blank=True, help_text="Away shorts colour")
    away_socks_colour    = models.CharField(max_length=50, blank=True, help_text="Away socks colour")
    away_gk_colour       = models.CharField(max_length=50, blank=True, help_text="Away goalkeeper jersey colour")
    away_kit_image       = models.ImageField(upload_to="kits/away/", null=True, blank=True, help_text="Photo of away kit")

    # Third kit (optional)
    third_outfield_colour = models.CharField(max_length=50, blank=True, help_text="Third outfield jersey colour")
    third_shorts_colour   = models.CharField(max_length=50, blank=True, help_text="Third shorts colour")
    third_socks_colour    = models.CharField(max_length=50, blank=True, help_text="Third socks colour")
    third_gk_colour       = models.CharField(max_length=50, blank=True, help_text="Third goalkeeper jersey colour")
    third_kit_image       = models.ImageField(upload_to="kits/third/", null=True, blank=True, help_text="Photo of third kit")

    # Legacy fields (kept for backward compat; prefer new kit fields above)
    home_colour = models.CharField(max_length=50, blank=True, help_text="Primary kit colour (legacy)")
    away_colour = models.CharField(max_length=50, blank=True)

    contact_phone = models.CharField(max_length=13, validators=[kenya_phone_validator])
    contact_email = models.EmailField(blank=True)

    # ── Qualification tracking (sub-county → county promotion) ────────────────
    qualified_to_county = models.BooleanField(
        default=False,
        help_text="True when this sub-county team has qualified to county finals",
    )
    qualifying_county_competition = models.ForeignKey(
        "competitions.Competition",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="qualified_teams",
        help_text="County competition this team qualified for",
    )

    # ── Payment tracking ───────────────────────────────────────────────────────
    payment_confirmed    = models.BooleanField(default=True, help_text="Registration cleared for competition participation")
    payment_reference    = models.CharField(max_length=100, blank=True, help_text="M-Pesa or receipt reference")
    payment_amount       = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Amount paid (KSh)")
    payment_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="payment_confirmations",
    )
    payment_confirmed_at = models.DateTimeField(null=True, blank=True)

    registered_at = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["county", "name"]

    def __str__(self):
        return self.name

    @property
    def home_kit_complete(self):
        """True if all mandatory home kit fields are filled."""
        return all([self.home_outfield_colour, self.home_shorts_colour,
                    self.home_socks_colour, self.home_gk_colour])

    @property
    def away_kit_complete(self):
        """True if all mandatory away kit fields are filled."""
        return all([self.away_outfield_colour, self.away_shorts_colour,
                    self.away_socks_colour, self.away_gk_colour])

    @property
    def kits_complete(self):
        """True if both home and away kit details are filled (required for approval)."""
        return self.home_kit_complete and self.away_kit_complete

    @staticmethod
    def normalize_player_position(raw_position, fallback=None):
        value = (raw_position or "").strip().upper()
        aliases = {
            "GOALKEEPER": "GK",
            "KEEPER": "GK",
            "CENTRE BACK": "CB",
            "CENTER BACK": "CB",
            "DEFENDER": "CB",
            "LEFT BACK": "LB",
            "RIGHT BACK": "RB",
            "DEFENSIVE MID": "CDM",
            "DEFENSIVE MIDFIELD": "CDM",
            "MIDFIELDER": "CM",
            "MIDFIELD": "CM",
            "ATTACKING MID": "AM",
            "ATTACKING MIDFIELD": "AM",
            "LEFT WING": "LW",
            "RIGHT WING": "RW",
            "CENTRE FORWARD": "CF",
            "CENTER FORWARD": "CF",
            "STRIKER": "ST",
            "FORWARD": "CF",
        }
        normalized = aliases.get(value, value)
        valid_codes = {choice[0] for choice in Position.choices}

        if normalized in valid_codes:
            return normalized
        if fallback in valid_codes:
            return fallback
        return Position.CM

    def sync_players_from_county_discipline(self):
        if not self.source_discipline_id:
            return 0

        synced_count = 0
        existing_players = list(self.players.all())
        existing_by_national_id = {
            p.national_id_number: p for p in existing_players if p.national_id_number
        }
        used_numbers = {p.shirt_number for p in existing_players if p.shirt_number}
        next_number = 1

        def allocate_shirt(preferred):
            nonlocal next_number
            if preferred and preferred not in used_numbers:
                used_numbers.add(preferred)
                return preferred
            while next_number in used_numbers:
                next_number += 1
            used_numbers.add(next_number)
            return next_number

        for county_player in self.source_discipline.players.all():
            team_player = existing_by_national_id.get(county_player.national_id_number)
            is_verified = county_player.verification_status == "verified"

            # Keep an existing player's number stable across repeated syncs.
            existing_number = team_player.shirt_number if team_player else None
            if existing_number:
                used_numbers.discard(existing_number)
            preferred_number = county_player.jersey_number or existing_number

            player_dob = county_player.date_of_birth
            fallback_position = team_player.position if team_player else None
            normalized_position = self.normalize_player_position(
                county_player.position,
                fallback=fallback_position,
            )

            defaults = {
                "team": self,
                "first_name": county_player.first_name,
                "last_name": county_player.last_name,
                "date_of_birth": player_dob,
                "position": normalized_position,
                "shirt_number": allocate_shirt(preferred_number),
                "birth_cert_number": county_player.huduma_number,
                "photo": county_player.photo,
                "id_document": county_player.id_document,
                "birth_certificate": county_player.birth_certificate,
                "verification_status": VerificationStatus.VERIFIED if is_verified else VerificationStatus.PENDING,
                "verified_at": timezone.now() if is_verified else None,
                "huduma_status": HudumaVerificationStatus.VERIFIED if is_verified and county_player.huduma_status != "failed" else HudumaVerificationStatus.NOT_CHECKED,
                "huduma_verified_at": county_player.huduma_verified_at,
                "fifa_connect_status": FIFAConnectStatus.CLEAR if is_verified and county_player.higher_league_status != "flagged" else FIFAConnectStatus.NOT_CHECKED,
                "fifa_connect_notes": county_player.higher_league_details,
                "status": PlayerStatus.ELIGIBLE if is_verified else PlayerStatus.INELIGIBLE,
            }

            if team_player is None:
                Player.objects.create(
                    national_id_number=county_player.national_id_number,
                    **defaults,
                )
                synced_count += 1
                continue

            updated_fields = []
            for field_name, value in defaults.items():
                if field_name == "team":
                    continue
                if getattr(team_player, field_name) != value:
                    setattr(team_player, field_name, value)
                    updated_fields.append(field_name)
            if updated_fields:
                team_player.save(update_fields=updated_fields)
                synced_count += 1

        return synced_count


class Position(models.TextChoices):
    GK  = "GK",  "Goalkeeper"
    CB  = "CB",  "Centre Back"
    LB  = "LB",  "Left Back"
    RB  = "RB",  "Right Back"
    CDM = "CDM", "Defensive Mid"
    CM  = "CM",  "Centre Mid"
    AM  = "AM",  "Attacking Mid"
    LW  = "LW",  "Left Wing"
    RW  = "RW",  "Right Wing"
    CF  = "CF",  "Centre Forward"
    ST  = "ST",  "Striker"


class PlayerStatus(models.TextChoices):
    ELIGIBLE   = "eligible",   "Eligible"
    INELIGIBLE = "ineligible", "Ineligible"
    SUSPENDED  = "suspended",  "Suspended"
    INJURED    = "injured",    "Injured"


class VerificationStatus(models.TextChoices):
    PENDING  = "pending",  "Pending Verification"
    VERIFIED = "verified", "Verified"
    REJECTED = "rejected", "Rejected"


class RejectionReason(models.TextChoices):
    FAKE_ID         = "fake_id",         "Fake / Invalid ID"
    FAKE_BIRTH_CERT = "fake_birth_cert", "Fake / Invalid Birth Certificate"
    PHOTO_MISMATCH  = "photo_mismatch",  "Photo Does Not Match"
    AGE_OUTSIDE     = "age_outside",     "Outside Age Bracket (18-23)"
    INCOMPLETE_DOCS = "incomplete_docs", "Incomplete Documents"
    FIFA_CONNECT_FLAGGED = "fifa_connect_flagged", "Flagged by FIFA Connect (Higher League)"
    HUDUMA_FAILED   = "huduma_failed",   "Huduma Kenya Verification Failed"
    OTHER           = "other",           "Other"


class HudumaVerificationStatus(models.TextChoices):
    NOT_CHECKED = "not_checked", "Not Checked"
    PENDING     = "pending",     "Pending Verification"
    VERIFIED    = "verified",    "Verified"
    FAILED      = "failed",      "Failed"
    EXPIRED     = "expired",     "Expired"


class FIFAConnectStatus(models.TextChoices):
    NOT_CHECKED = "not_checked", "Not Checked"
    PENDING     = "pending",     "Pending Check"
    CLEAR       = "clear",       "Clear - No Higher League"
    FLAGGED     = "flagged",     "Flagged - Higher League Found"
    ERROR       = "error",       "API Error"


class HigherLeague(models.TextChoices):
    REGIONAL_LEAGUE      = "regional_league",      "Regional League"
    DIVISION_TWO         = "division_two",         "Division Two"
    DIVISION_ONE         = "division_one",         "Division One"
    NATIONAL_SUPER_LEAGUE = "national_super_league", "National Super League"
    FKF_PREMIER_LEAGUE   = "fkf_premier_league",   "Kenya FKF Premier League"


# Age bracket constants
PLAYER_MIN_AGE = 18
PLAYER_MAX_AGE = 23


class Player(models.Model):
    team           = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="players")
    first_name     = models.CharField(max_length=100)
    last_name      = models.CharField(max_length=100)
    date_of_birth  = models.DateField(null=True, blank=True)
    position       = models.CharField(max_length=10, choices=Position.choices)
    shirt_number       = models.PositiveIntegerField()
    national_id_number = models.CharField(max_length=20, blank=True, default="", validators=[national_id_validator],
                                          help_text="National ID number")
    birth_cert_number  = models.CharField(max_length=30, blank=True, default="",
                                          help_text="Birth Certificate number")

    # ── Document uploads for verification ─────────────────────────────────
    photo          = models.ImageField(upload_to="players/photos/", null=True, blank=True,
                                       help_text="Passport-size photo")
    id_document    = models.ImageField(upload_to="players/ids/", null=True, blank=True,
                                       help_text="Copy of National ID")
    birth_certificate = models.ImageField(upload_to="players/birth_certs/", null=True, blank=True,
                                          help_text="Copy of Birth Certificate")

    # ── Verification workflow ─────────────────────────────────────────────
    verification_status = models.CharField(
        max_length=20, choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
    )
    rejection_reason = models.CharField(
        max_length=30, choices=RejectionReason.choices,
        blank=True, default="",
    )
    rejection_notes  = models.TextField(blank=True, default="",
                                        help_text="Additional notes on rejection")
    verified_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="verified_players",
    )
    verified_at      = models.DateTimeField(null=True, blank=True)

    # ── Huduma Kenya Verification (Age) ───────────────────────────────────
    huduma_status = models.CharField(
        max_length=20, choices=HudumaVerificationStatus.choices,
        default=HudumaVerificationStatus.NOT_CHECKED,
        help_text="Huduma Kenya age verification status",
    )
    huduma_verified_at  = models.DateTimeField(null=True, blank=True)
    huduma_verified_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="huduma_verified_players",
    )
    huduma_reference    = models.CharField(max_length=100, blank=True, default="",
                                           help_text="Huduma Kenya verification reference")
    huduma_notes        = models.TextField(blank=True, default="",
                                           help_text="Notes from Huduma verification")

    # ── FIFA Connect Verification (Higher League Check) ───────────────────
    fifa_connect_id     = models.CharField(max_length=50, blank=True, default="",
                                           help_text="FIFA Connect Player ID")
    fifa_connect_status = models.CharField(
        max_length=20, choices=FIFAConnectStatus.choices,
        default=FIFAConnectStatus.NOT_CHECKED,
        help_text="FIFA Connect higher-league check status",
    )
    fifa_connect_leagues = models.JSONField(
        default=list, blank=True,
        help_text="List of higher-level leagues found in FIFA Connect",
    )
    fifa_connect_checked_at = models.DateTimeField(null=True, blank=True)
    fifa_connect_checked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="fifa_connect_checked_players",
    )
    fifa_connect_notes = models.TextField(blank=True, default="",
                                          help_text="Notes from FIFA Connect check")

    status         = models.CharField(max_length=20, choices=PlayerStatus.choices, default=PlayerStatus.ELIGIBLE)
    registered_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["team", "shirt_number"]
        ordering        = ["team", "shirt_number"]

    def __str__(self):
        return f"#{self.shirt_number} {self.first_name} {self.last_name} ({self.team})"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self):
        from django.utils import timezone
        dob = self.date_of_birth
        if not dob:
            return None
        today = timezone.now().date()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    @property
    def is_age_eligible(self):
        """True if the player falls within the 18 - 23 age bracket."""
        if self.age is None:
            return True
        return PLAYER_MIN_AGE <= self.age <= PLAYER_MAX_AGE

    @property
    def documents_uploaded(self):
        """True if required documents (photo + ID) are present. Birth certificate is optional."""
        return bool(self.photo and self.id_document)

    @property
    def is_huduma_verified(self):
        """True if Huduma Kenya age verification has passed."""
        return self.huduma_status == HudumaVerificationStatus.VERIFIED

    @property
    def is_fifa_connect_clear(self):
        """True if FIFA Connect check found no higher-league registration."""
        return self.fifa_connect_status == FIFAConnectStatus.CLEAR

    @property
    def is_fully_cleared(self):
        """
        True ONLY if the player passes ALL verification steps:
        1. Document verification (admin verified)
        2. Huduma Kenya age verification
        3. FIFA Connect higher-league check is clear
        """
        return (
            self.verification_status == VerificationStatus.VERIFIED
            and self.is_huduma_verified
            and self.is_fifa_connect_clear
        )

    @property
    def clearance_summary(self):
        """Return a dict summarising each verification step."""
        return {
            'documents': {
                'status': self.verification_status,
                'display': self.get_verification_status_display(),
                'passed': self.verification_status == VerificationStatus.VERIFIED,
            },
            'huduma': {
                'status': self.huduma_status,
                'display': self.get_huduma_status_display(),
                'passed': self.is_huduma_verified,
            },
            'fifa_connect': {
                'status': self.fifa_connect_status,
                'display': self.get_fifa_connect_status_display(),
                'passed': self.is_fifa_connect_clear,
                'leagues_found': self.fifa_connect_leagues,
            },
            'fully_cleared': self.is_fully_cleared,
        }

    def auto_check_age(self):
        """
        Automatically lock out players outside the 18-23 bracket.
        Called on save. Sets status to ineligible and rejection reason.
        """
        if self.age is None:
            return True
        if not self.is_age_eligible:
            self.verification_status = VerificationStatus.REJECTED
            self.rejection_reason = RejectionReason.AGE_OUTSIDE
            self.rejection_notes = (
                f"Player is {self.age} years old. "
                f"Must be between {PLAYER_MIN_AGE} and {PLAYER_MAX_AGE}."
            )
            self.status = PlayerStatus.INELIGIBLE
            return False
        return True

    def save(self, *args, **kwargs):
        # Auto-reject players outside the age bracket on every save
        self.auto_check_age()
        super().save(*args, **kwargs)


# ══════════════════════════════════════════════════════════════════════════════
#  PLAYER VERIFICATION LOG - Audit Trail
# ══════════════════════════════════════════════════════════════════════════════

class VerificationStep(models.TextChoices):
    DOCUMENT   = "document",     "Document Verification"
    HUDUMA     = "huduma",       "Huduma Kenya (Age)"
    FIFA_CONNECT = "fifa_connect", "FIFA Connect (League Check)"
    CLEARANCE  = "clearance",    "Final Clearance"


class PlayerVerificationLog(models.Model):
    """Records every verification action for audit trail."""
    player      = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="verification_logs")
    step        = models.CharField(max_length=20, choices=VerificationStep.choices)
    action      = models.CharField(max_length=50, help_text="e.g. 'verified', 'rejected', 'flagged', 'cleared'")
    result      = models.CharField(max_length=50, help_text="Outcome of the action")
    details     = models.JSONField(default=dict, blank=True, help_text="Detailed data from the verification")
    notes       = models.TextField(blank=True, default="")
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="verification_actions",
    )
    performed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-performed_at"]
        verbose_name = "Verification Log"
        verbose_name_plural = "Verification Logs"

    def __str__(self):
        return f"{self.player.get_full_name()} - {self.get_step_display()} - {self.action}"


# ══════════════════════════════════════════════════════════════════════════════
#   SCOUT SHORTLIST
# ══════════════════════════════════════════════════════════════════════════════

class ScoutShortlist(models.Model):
    """A scout's shortlisted player with notes and rating."""
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]

    scout = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="scout_shortlists",
        limit_choices_to={"role": "scout"},
    )
    player = models.ForeignKey(
        CountyPlayer, on_delete=models.CASCADE,
        related_name="scout_entries",
    )
    rating = models.PositiveSmallIntegerField(
        choices=RATING_CHOICES, default=3,
        help_text="1 = Low potential, 5 = Outstanding",
    )
    notes = models.TextField(blank=True, default="", help_text="Scouting notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("scout", "player")
        ordering = ["-updated_at"]
        verbose_name = "Scout Shortlist Entry"
        verbose_name_plural = "Scout Shortlist Entries"

    def __str__(self):
        return f"{self.scout.get_full_name()} → {self.player.first_name} {self.player.last_name} ({self.rating}★)"


class ScoutShortlistSubmissionStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Final List Submitted"
    EDIT_REQUESTED = "edit_requested", "Edit Access Requested"
    EDIT_APPROVED = "edit_approved", "Edit Access Approved"
    EDIT_DENIED = "edit_denied", "Edit Access Denied"


class ScoutShortlistSubmission(models.Model):
    """Tracks final shortlist submission state for each scout."""

    scout = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="scout_shortlist_submission",
        limit_choices_to={"role": "scout"},
    )
    status = models.CharField(
        max_length=20,
        choices=ScoutShortlistSubmissionStatus.choices,
        default=ScoutShortlistSubmissionStatus.DRAFT,
    )
    final_submitted_at = models.DateTimeField(null=True, blank=True)
    edit_requested_at = models.DateTimeField(null=True, blank=True)
    edit_request_reason = models.TextField(blank=True, default="")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scout_shortlist_reviews",
    )
    review_notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Scout Shortlist Submission"
        verbose_name_plural = "Scout Shortlist Submissions"

    def __str__(self):
        return f"{self.scout.get_full_name()} - {self.get_status_display()}"

    @property
    def can_edit(self):
        return self.status in {
            ScoutShortlistSubmissionStatus.DRAFT,
            ScoutShortlistSubmissionStatus.EDIT_APPROVED,
        }

    @property
    def is_locked(self):
        return not self.can_edit

    @property
    def can_request_edit(self):
        return self.status in {
            ScoutShortlistSubmissionStatus.SUBMITTED,
            ScoutShortlistSubmissionStatus.EDIT_DENIED,
        }


# ══════════════════════════════════════════════════════════════════════════════
#   SCOUTING CRITERIA - INTERNATIONAL STANDARDS PER DISCIPLINE
# ══════════════════════════════════════════════════════════════════════════════

SCOUTING_CRITERIA = {
    "football": {
        "label": "Football (FIFA)",
        "criteria": [
            {"key": "technical", "label": "Technical Ability", "description": "Ball control, first touch, passing accuracy, dribbling, shooting technique"},
            {"key": "tactical", "label": "Tactical Awareness", "description": "Positioning, decision making, reading of play, spatial awareness, game intelligence"},
            {"key": "physical", "label": "Physical Attributes", "description": "Speed, stamina, strength, agility, balance, acceleration"},
            {"key": "mental", "label": "Mental Attributes", "description": "Composure, leadership, work rate, concentration, resilience, communication"},
            {"key": "attacking", "label": "Attacking Play", "description": "Movement off the ball, finishing, crossing, chance creation, link-up play"},
            {"key": "defending", "label": "Defensive Play", "description": "Tackling, interceptions, aerial duels, marking, recovery runs"},
        ],
        "gk_criteria": [
            {"key": "shot_stopping", "label": "Shot Stopping", "description": "Reflexes, diving, positioning, one-on-one saves"},
            {"key": "distribution", "label": "Distribution", "description": "Goal kicks, throwing, passing accuracy under pressure"},
            {"key": "command_of_area", "label": "Command of Area", "description": "Cross collection, communication, sweeping, set piece organisation"},
            {"key": "footwork", "label": "Footwork", "description": "Ability with feet, composure on the ball, short passing"},
        ],
    },
    "volleyball": {
        "label": "Volleyball (FIVB)",
        "criteria": [
            {"key": "serving", "label": "Serving", "description": "Accuracy, power, float serve, jump serve, tactical serving"},
            {"key": "passing", "label": "Passing / Reception", "description": "Serve receive quality, platform control, first ball accuracy"},
            {"key": "setting", "label": "Setting", "description": "Hand setting technique, back setting, quick sets, decision making"},
            {"key": "attacking", "label": "Attacking / Spiking", "description": "Hitting power, shot selection, timing, approach technique"},
            {"key": "blocking", "label": "Blocking", "description": "Timing, footwork, read blocking, positioning, penetration"},
            {"key": "digging", "label": "Digging / Defense", "description": "Floor defense, reaction time, platform control, court coverage"},
        ],
    },
    "basketball": {
        "label": "Basketball (FIBA)",
        "criteria": [
            {"key": "shooting", "label": "Shooting", "description": "Mid-range, 3-point, free throw, shooting form, shot selection"},
            {"key": "ball_handling", "label": "Ball Handling", "description": "Dribbling, crossovers, change of pace, ball security, finishing at rim"},
            {"key": "passing", "label": "Passing & Court Vision", "description": "Accuracy, creativity, decision making, fast break passing"},
            {"key": "rebounding", "label": "Rebounding", "description": "Positioning, box out, timing, effort on offensive & defensive boards"},
            {"key": "defense", "label": "Defense", "description": "On-ball defense, help defense, steals, shot blocking, rotations"},
            {"key": "athleticism", "label": "Athleticism", "description": "Speed, vertical leap, lateral quickness, endurance, strength"},
        ],
    },
    "basketball_5x5": {
        "label": "Basketball 5×5 (FIBA)",
        "criteria": [
            {"key": "shooting", "label": "Shooting", "description": "Mid-range, 3-point, free throw, shooting form, shot selection"},
            {"key": "ball_handling", "label": "Ball Handling", "description": "Dribbling, crossovers, change of pace, ball security, finishing at rim"},
            {"key": "passing", "label": "Passing & Court Vision", "description": "Accuracy, creativity, decision making, fast break passing"},
            {"key": "rebounding", "label": "Rebounding", "description": "Positioning, box out, timing, effort on offensive & defensive boards"},
            {"key": "defense", "label": "Defense", "description": "On-ball defense, help defense, steals, shot blocking, rotations"},
            {"key": "athleticism", "label": "Athleticism", "description": "Speed, vertical leap, lateral quickness, endurance, strength"},
        ],
    },
    "basketball_3x3": {
        "label": "Basketball 3×3 (FIBA)",
        "criteria": [
            {"key": "shooting", "label": "Shooting", "description": "Mid-range, 2-point (arc), free throw, catch-and-shoot"},
            {"key": "ball_handling", "label": "Ball Handling", "description": "Dribbling, isolation moves, 1-on-1 ability, ball security"},
            {"key": "passing", "label": "Passing & Court Vision", "description": "Quick decision making, pick-and-roll reads, skip passes"},
            {"key": "defense", "label": "Defense", "description": "On-ball pressure, switches, help-and-recover, checking the ball"},
            {"key": "versatility", "label": "Versatility", "description": "Positionless play, ability to guard multiple positions, transition play"},
        ],
    },
    "handball": {
        "label": "Handball (IHF)",
        "criteria": [
            {"key": "throwing", "label": "Throwing", "description": "Power, accuracy, variety - jump shot, spin shot, hip shot, lob"},
            {"key": "passing", "label": "Passing", "description": "Accuracy, speed, creativity, bounce pass, lob pass"},
            {"key": "dribbling", "label": "Dribbling & Ball Handling", "description": "Ball control, speed dribble, change of direction"},
            {"key": "defense", "label": "Defensive Play", "description": "Positioning, blocking, tackling, interceptions, 6-0 / 5-1 systems"},
            {"key": "movement", "label": "Movement & Positioning", "description": "Off-ball movement, fast break, wing play, pivot play"},
            {"key": "physical", "label": "Physical Attributes", "description": "Power, speed, endurance, agility, body contact resilience"},
        ],
        "gk_criteria": [
            {"key": "shot_stopping", "label": "Shot Stopping", "description": "Reflexes, positioning, angle play, penalty saving, near-post saves"},
            {"key": "distribution", "label": "Distribution", "description": "Fast break initiation, throwing accuracy, decision making"},
        ],
    },
}


def get_scouting_criteria(sport_type):
    """Return scouting criteria dict for a sport_type, falling back to sport family."""
    from matches.models import get_sport_family
    family = get_sport_family(sport_type)
    return SCOUTING_CRITERIA.get(family, SCOUTING_CRITERIA.get("football"))


# ══════════════════════════════════════════════════════════════════════════════
#   SCOUT REPORT - DETAILED PLAYER EVALUATION
# ══════════════════════════════════════════════════════════════════════════════

class ScoutReport(models.Model):
    """Detailed scouting evaluation of a player observed during a specific match."""
    RECOMMENDATION_CHOICES = [
        ("highly_recommended", "Highly Recommended"),
        ("recommended", "Recommended"),
        ("monitor", "Continue Monitoring"),
        ("not_recommended", "Not Recommended"),
    ]

    scout = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="scout_reports",
        limit_choices_to={"role": "scout"},
    )
    player = models.ForeignKey(
        "teams.Player", on_delete=models.CASCADE,
        related_name="scout_reports",
    )
    fixture = models.ForeignKey(
        "competitions.Fixture", on_delete=models.CASCADE,
        related_name="scout_reports",
    )
    sport_type = models.CharField(max_length=30, blank=True)

    # Sport-specific criteria scores: {"technical": 8, "tactical": 7, ...}
    criteria_scores = models.JSONField(default=dict)
    overall_rating = models.PositiveSmallIntegerField(
        help_text="Overall rating 1 - 10",
    )

    strengths = models.TextField(blank=True)
    weaknesses = models.TextField(blank=True)
    recommendation = models.CharField(max_length=20, choices=RECOMMENDATION_CHOICES)
    notes = models.TextField(blank=True)
    minutes_observed = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("scout", "player", "fixture")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Scout Report: {self.player} @ {self.fixture} by {self.scout.get_full_name()}"

    @property
    def criteria_display(self):
        """Return list of (label, score) for template display."""
        sc = get_scouting_criteria(self.sport_type)
        criteria_list = sc.get("criteria", [])
        result = []
        for c in criteria_list:
            score = self.criteria_scores.get(c["key"])
            if score is not None:
                result.append({"label": c["label"], "score": score, "key": c["key"]})
        # also include GK criteria if present
        for c in sc.get("gk_criteria", []):
            score = self.criteria_scores.get(c["key"])
            if score is not None:
                result.append({"label": c["label"], "score": score, "key": c["key"]})
        return result


# ══════════════════════════════════════════════════════════════════════════════
#  BULK PLAYER UPLOAD  (Chief Sports Officer / Admin → Director Sports approval)
# ══════════════════════════════════════════════════════════════════════════════

class BulkUploadStatus(models.TextChoices):
    PENDING  = "pending",  "Pending Approval"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class BulkPlayerUpload(models.Model):
    """
    A bulk player upload batch.  The Chief Sports Officer (or Admin) uploads
    an Excel file; the system parses each row into BulkPlayerUploadRow.
    Director of Sports approves or rejects the entire batch.
    On approval, rows are converted into verified CountyPlayer records.
    """
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="bulk_uploads",
    )
    file = models.FileField(
        upload_to="bulk_uploads/%Y/%m/",
        help_text="Excel (.xlsx) or Word (.docx) file with player data",
    )
    original_filename = models.CharField(max_length=255, blank=True, default="")
    sport_type = models.CharField(max_length=30, choices=SportType.choices)
    sub_county = models.CharField(max_length=100, choices=MakueniSubCounty.choices)
    status = models.CharField(
        max_length=20, choices=BulkUploadStatus.choices,
        default=BulkUploadStatus.PENDING,
    )
    notes = models.TextField(blank=True, default="", help_text="Uploader notes")
    rejection_reason = models.TextField(blank=True, default="")
    uploaded_by_role = models.CharField(
        max_length=30, blank=True, default="",
        help_text="Role of the user who uploaded (coordinator, chief_sports_officer, etc.)",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="bulk_uploads_reviewed",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    # Two-step approval for coordinator uploads
    cso_approved = models.BooleanField(default=False, help_text="Chief Sports Officer approved")
    cso_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="bulk_uploads_cso_approved",
    )
    cso_approved_at = models.DateTimeField(null=True, blank=True)
    ds_approved = models.BooleanField(default=False, help_text="Director Sports approved")
    ds_approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="bulk_uploads_ds_approved",
    )
    ds_approved_at = models.DateTimeField(null=True, blank=True)
    total_rows = models.PositiveIntegerField(default=0)
    valid_rows = models.PositiveIntegerField(default=0)
    error_rows = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Bulk Upload #{self.pk} - {self.get_sport_type_display()} ({self.sub_county}) - {self.get_status_display()}"


class BulkPlayerUploadRow(models.Model):
    """Individual player row from a bulk upload."""
    upload = models.ForeignKey(
        BulkPlayerUpload, on_delete=models.CASCADE,
        related_name="rows",
    )
    row_number = models.PositiveIntegerField()
    full_name = models.CharField(max_length=200, blank=True, default="",
                                  help_text="Full name as per ID document")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField(null=True, blank=True)
    national_id_number = models.CharField(max_length=20, blank=True, default="")
    phone = models.CharField(max_length=20, blank=True, default="")
    position = models.CharField(max_length=30, blank=True, default="")
    jersey_number = models.PositiveIntegerField(null=True, blank=True)
    ward = models.CharField(max_length=100, blank=True, default="")
    ligi_mashinani_team = models.CharField(max_length=200, blank=True, default="",
                                            help_text="Team in Ligi Mashinani")
    age_value = models.PositiveIntegerField(null=True, blank=True,
                                             help_text="Player age (when DOB not available)")
    remarks = models.TextField(blank=True, default="",
                                help_text="Remarks from the uploaded file")
    reason_for_change = models.TextField(blank=True, default="",
                                          help_text="Reason for change from the uploaded file")
    is_valid = models.BooleanField(default=True)
    error_message = models.TextField(blank=True, default="")
    county_player = models.ForeignKey(
        'CountyPlayer', on_delete=models.SET_NULL,
        null=True, blank=True, related_name="bulk_source",
        help_text="CountyPlayer created from this row on approval",
    )
    # Edit tracking
    edit_reason = models.TextField(blank=True, default="",
                                    help_text="Reason for editing this row (required on edit)")
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="bulk_row_edits",
    )
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["row_number"]
        unique_together = ["upload", "row_number"]

    def __str__(self):
        return f"Row {self.row_number}: {self.full_name or (self.first_name + ' ' + self.last_name)}"


# ══════════════════════════════════════════════════════════════════════════════
#  LIGI MASHINANI REGISTRATION
#  Public-facing ward-level team manager pre-registration.
#  Pending → Ward Sports Council Verified → System Admin Approved → Account Created
# ══════════════════════════════════════════════════════════════════════════════

class LigiMashinaniStatus(models.TextChoices):
    PENDING      = "pending",      "Pending Ward Verification"
    WARD_VERIFIED = "ward_verified", "Ward Sports Council Verified"
    APPROVED     = "approved",     "System Admin Approved"
    REJECTED     = "rejected",     "Rejected"


LIGI_DISCIPLINE_CHOICES = [
    ('football_men',        'Soccer (Men)'),
    ('football_women',      'Soccer (Women)'),
    ('volleyball_men',      'Volleyball (Men)'),
    ('volleyball_women',    'Volleyball (Women)'),
    ('basketball_men',      'Basketball 5x5 (Men)'),
    ('basketball_women',    'Basketball 5x5 (Women)'),
    ('basketball_3x3_men',  'Basketball 3x3 (Men)'),
    ('basketball_3x3_women','Basketball 3x3 (Women)'),
    ('handball_men',        'Handball (Men)'),
    ('handball_women',      'Handball (Women)'),
]


class LigiMashinaniRegistration(models.Model):
    """
    A team manager registers their Ligi Mashinani / ward team online.
    The registration starts as 'pending', is verified by the ward sports
    council chair, then approved by the system admin who creates their portal account.
    """
    sub_county = models.CharField(max_length=100, help_text="Makueni sub-county")
    ward       = models.CharField(max_length=100, help_text="Ward within the sub-county")

    team_name  = models.CharField(max_length=200, help_text="Ward / Ligi Mashinani team name")
    discipline = models.CharField(
        max_length=30, choices=LIGI_DISCIPLINE_CHOICES,
        help_text="Sport discipline",
    )

    manager_first_name = models.CharField(max_length=100, help_text="Team manager first name")
    manager_last_name  = models.CharField(max_length=100, help_text="Team manager last name")
    manager_email      = models.EmailField(unique=True, help_text="Team manager email address")
    manager_phone      = models.CharField(max_length=13, help_text="WhatsApp-enabled phone number (+254...)")

    status = models.CharField(
        max_length=20, choices=LigiMashinaniStatus.choices,
        default=LigiMashinaniStatus.PENDING,
        help_text="Registration approval status",
    )
    rejection_reason = models.TextField(blank=True, default="")

    # Set to True once a portal account has been auto-created on admin approval
    account_created = models.BooleanField(
        default=False,
        help_text="Portal (Team Manager) account auto-created for this manager",
    )

    submitted_at = models.DateTimeField(default=timezone.now)
    updated_at   = models.DateTimeField(auto_now=True)
    notes        = models.TextField(blank=True, default="", help_text="Internal admin notes")

    class Meta:
        verbose_name          = "Ligi Mashinani Registration"
        verbose_name_plural   = "Ligi Mashinani Registrations"
        ordering              = ["-submitted_at"]

    def __str__(self):
        return (
            f"{self.team_name} | {self.ward}, {self.sub_county} "
            f"| {self.get_discipline_display()} | {self.get_status_display()}"
        )

    @property
    def manager_full_name(self):
        return f"{self.manager_first_name} {self.manager_last_name}".strip()

    def get_discipline_display(self):
        return dict(LIGI_DISCIPLINE_CHOICES).get(self.discipline, self.discipline)

    def clean_discipline(self):
        """Validate that discipline is one of the ten supported LIGI_DISCIPLINE_CHOICES.
        Raises ValidationError identifying the discipline field if invalid.
        Requirements: 9.1, 9.2
        """
        from django.core.exceptions import ValidationError as _VE
        valid_keys = {d[0] for d in LIGI_DISCIPLINE_CHOICES}
        if self.discipline and self.discipline not in valid_keys:
            raise _VE(
                {'discipline': (
                    f'"{self.discipline}" is not a supported discipline. '
                    f'Choose one of: {", ".join(dict(LIGI_DISCIPLINE_CHOICES).values())}.'
                )},
            )
        return self.discipline

    def clean(self):
        """Full model validation — enforces discipline choices constraint.
        Requirements: 9.1, 9.2
        """
        from django.core.exceptions import ValidationError as _VE
        errors = {}
        valid_keys = {d[0] for d in LIGI_DISCIPLINE_CHOICES}
        if self.discipline and self.discipline not in valid_keys:
            errors['discipline'] = (
                f'"{self.discipline}" is not a supported discipline. '
                f'Choose one of: {", ".join(dict(LIGI_DISCIPLINE_CHOICES).values())}.'
            )
        if errors:
            raise _VE(errors)


# ══════════════════════════════════════════════════════════════════════════════
#  LIGI MASHINANI SYSTEM SETTINGS (singleton)
#  Controlled by Chief Sports Officer, Director of Sports, and System Admin.
#  Opens / closes: team registration, player registration, and transfer window.
# ══════════════════════════════════════════════════════════════════════════════

class LigiSettings(models.Model):
    """
    Singleton settings record controlling which Ligi Mashinani windows are open.

    Only one row ever exists (pk=1).  Use LigiSettings.get() to read values.
    Authorised roles: chief_sports_officer, director_sports, admin.
    """
    # ── Team registration (LigiMashinaniRegistration submissions) ─────────
    team_registration_open = models.BooleanField(
        default=True,
        help_text="Allow new Ligi Mashinani team registrations on the public homepage.",
    )
    team_registration_closed_message = models.CharField(
        max_length=300,
        blank=True,
        default="Team registration for Ligi Mashinani is currently closed.",
        help_text="Message shown to the public when team registration is closed.",
    )

    # ── Player registration (Ward TM adding players to longlist) ──────────
    player_registration_open = models.BooleanField(
        default=True,
        help_text="Allow Ward Team Managers to add players to their ward longlist.",
    )
    player_registration_closed_message = models.CharField(
        max_length=300,
        blank=True,
        default="Player registration for Ligi Mashinani is currently closed.",
        help_text="Message shown to Ward TM when player registration is closed.",
    )

    # ── Transfer window ───────────────────────────────────────────────────
    transfer_window_open = models.BooleanField(
        default=False,
        help_text="Allow player transfers between ward teams during the transfer window.",
    )
    transfer_window_closed_message = models.CharField(
        max_length=300,
        blank=True,
        default="The Ligi Mashinani transfer window is currently closed.",
        help_text="Message shown to Ward TM when the transfer window is closed.",
    )

    # ── Registration deadline (drives public countdown) ───────────────────
    registration_deadline = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "Optional deadline datetime for team registration. "
            "Shown as a live countdown on the public homepage. "
            "Leave blank to hide the countdown."
        ),
    )

    # ── Audit trail ───────────────────────────────────────────────────────
    last_changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="ligi_settings_changes",
        help_text="Last user to change these settings.",
    )
    last_changed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ligi Mashinani Settings"
        verbose_name_plural = "Ligi Mashinani Settings"

    def __str__(self):
        flags = []
        if self.team_registration_open:
            flags.append("TeamReg✓")
        if self.player_registration_open:
            flags.append("PlayerReg✓")
        if self.transfer_window_open:
            flags.append("Transfer✓")
        return "LigiSettings [" + ", ".join(flags) + "]" if flags else "LigiSettings [all closed]"

    @classmethod
    def get(cls):
        """Return the singleton instance, creating it with defaults if absent."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# ══════════════════════════════════════════════════════════════════════════════
#  LIGI MASHINANI TRANSFER REQUEST
#  Ward TM requests player transfer → WSCC approves → SCSO final approval.
#  Only active when LigiSettings.transfer_window_open = True.
# ══════════════════════════════════════════════════════════════════════════════

class LigiTransferStatus(models.TextChoices):
    PENDING        = "pending",        "Pending Review"
    WSCC_APPROVED  = "wscc_approved",  "WSCC Approved — Pending SCSO"
    WSCC_REJECTED  = "wscc_rejected",  "Rejected by WSCC"
    SCSO_APPROVED  = "scso_approved",  "Approved — Transfer Complete"
    SCSO_REJECTED  = "scso_rejected",  "Rejected by Sub-County Officer"
    SENIOR_APPROVED = "senior_approved", "Approved by Senior Official"
    SENIOR_REJECTED = "senior_rejected", "Rejected by Senior Official"
    WITHDRAWN      = "withdrawn",      "Withdrawn by Team Manager"


class LigiTransferType(models.TextChoices):
    WITHIN_WARD    = "within_ward",    "Within Same Ward (Team to Team)"
    INTER_WARD     = "inter_ward",     "Inter-Ward (Same Sub-County)"
    INTER_SUBCOUNTY = "inter_subcounty", "Inter-Sub-County"
    WSCC_REJECTED  = "wscc_rejected",  "Rejected by WSCC"
    SCSO_APPROVED  = "scso_approved",  "Approved — Transfer Complete"
    SCSO_REJECTED  = "scso_rejected",  "Rejected by Sub-County Officer"
    WITHDRAWN      = "withdrawn",      "Withdrawn by Team Manager"


class LigiTransferRequest(models.Model):
    """
    A Ward Team Manager requests to transfer a player to a different ward team
    within the same sub-county and discipline.

    Approval chain:
        Ward TM submits → WSCC approves/rejects → SCSO final approve/reject

    On SCSO approval:
        - player.discipline is updated to the destination discipline
        - player.ward is updated to the destination ward
        - Original discipline's WardLonglist can no longer count the player
    """
    player = models.ForeignKey(
        CountyPlayer,
        on_delete=models.CASCADE,
        related_name="transfer_requests",
        help_text="The player being transferred",
    )
    from_discipline = models.ForeignKey(
        CountyDiscipline,
        on_delete=models.CASCADE,
        related_name="outgoing_transfers",
        help_text="Source ward discipline (where the player currently plays)",
    )
    to_discipline = models.ForeignKey(
        CountyDiscipline,
        on_delete=models.CASCADE,
        related_name="incoming_transfers",
        help_text="Destination ward discipline (where the player wants to go)",
    )
    reason = models.TextField(
        help_text="Reason for transfer request (required)",
    )
    transfer_type = models.CharField(
        max_length=20,
        choices=LigiTransferType.choices,
        default=LigiTransferType.INTER_WARD,
        help_text="Auto-computed: within_ward / inter_ward / inter_subcounty",
    )
    status = models.CharField(
        max_length=20,
        choices=LigiTransferStatus.choices,
        default=LigiTransferStatus.PENDING,
    )

    # ── WSCC review ───────────────────────────────────────────────────────
    wscc_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wscc_transfer_reviews",
        help_text="WSCC who reviewed this request",
    )
    wscc_reviewed_at = models.DateTimeField(null=True, blank=True)
    wscc_notes = models.TextField(blank=True, default="",
                                  help_text="WSCC approval/rejection notes")

    # ── SCSO review ───────────────────────────────────────────────────────
    scso_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="scso_transfer_reviews",
        help_text="SCSO who gave final approval",
    )
    scso_reviewed_at = models.DateTimeField(null=True, blank=True)
    scso_notes = models.TextField(blank=True, default="",
                                  help_text="SCSO approval/rejection notes")

    # ── Senior official review (for inter-sub-county transfers) ─────────
    senior_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="senior_transfer_reviews",
        help_text="CSO/Director/Admin who reviewed inter-sub-county transfers",
    )
    senior_reviewed_at = models.DateTimeField(null=True, blank=True)
    senior_notes = models.TextField(blank=True, default="")

    # ── Timestamps ────────────────────────────────────────────────────────
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="transfer_requests_made",
        help_text="Ward TM who submitted this request",
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True,
                                        help_text="When transfer was finalised")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-requested_at"]
        verbose_name = "Ligi Transfer Request"
        verbose_name_plural = "Ligi Transfer Requests"

    def __str__(self):
        return (
            f"Transfer: {self.player.first_name} {self.player.last_name} "
            f"from {self.from_discipline.ward} → {self.to_discipline.ward} "
            f"[{self.get_status_display()}]"
        )

    @property
    def is_pending_wscc(self):
        return self.status == LigiTransferStatus.PENDING

    @property
    def is_pending_scso(self):
        return self.status == LigiTransferStatus.WSCC_APPROVED

    @property
    def is_complete(self):
        return self.status == LigiTransferStatus.SCSO_APPROVED

    @property
    def is_rejected(self):
        return self.status in (
            LigiTransferStatus.WSCC_REJECTED,
            LigiTransferStatus.SCSO_REJECTED,
        )


# ══════════════════════════════════════════════════════════════════════════════
#  WARD SUBSTITUTION REQUEST (Ligi Mashinani)
#  Mirrors SubstitutionRequest but uses CountyPlayer FK.
#  Ward TM requests → WSCC/4th official approves → executed.
# ══════════════════════════════════════════════════════════════════════════════

class WardSubstitutionStatus(models.TextChoices):
    REQUESTED = "requested", "Requested"
    APPROVED  = "approved",  "Approved"
    EXECUTED  = "executed",  "Executed"
    DENIED    = "denied",    "Denied"


class WardSubstitutionRequest(models.Model):
    """
    Substitution request for Ligi Mashinani ward-level fixtures.
    Uses CountyPlayer (not Player) because ward players are stored as CountyPlayer records.
    """
    fixture    = models.ForeignKey(
        "competitions.Fixture",
        on_delete=models.CASCADE,
        related_name="ward_substitution_requests",
    )
    team = models.ForeignKey(
        "teams.Team",
        on_delete=models.CASCADE,
        related_name="ward_substitution_requests",
    )
    player_off = models.ForeignKey(
        "teams.CountyPlayer",
        on_delete=models.CASCADE,
        related_name="ward_subbed_off",
        help_text="Ward player coming off",
    )
    player_on = models.ForeignKey(
        "teams.CountyPlayer",
        on_delete=models.CASCADE,
        related_name="ward_subbed_on",
        help_text="Ward player coming on",
    )
    minute = models.PositiveIntegerField(help_text="Match minute")
    status = models.CharField(
        max_length=12,
        choices=WardSubstitutionStatus.choices,
        default=WardSubstitutionStatus.REQUESTED,
    )
    reason = models.TextField(blank=True, default="")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="ward_sub_requests_made",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="ward_sub_requests_approved",
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_at   = models.DateTimeField(null=True, blank=True)
    denial_reason = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["fixture", "minute"]
        verbose_name = "Ward Substitution Request"
        verbose_name_plural = "Ward Substitution Requests"

    def __str__(self):
        return (
            f"Ward Sub: {self.player_off.first_name} → {self.player_on.first_name} "
            f"min {self.minute} [{self.get_status_display()}]"
        )
