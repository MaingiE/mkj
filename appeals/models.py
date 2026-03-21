"""
MKJ SUPA CUP Appeals — Jury & Appeals Management System Models

Workflow:
1. Team Manager submits appeal (with mandatory evidence + fee payment)
2. Respondent team submits response (with mandatory evidence)
3. Chair of the Jury reviews and makes a decision (with mandatory evidence/reasoning)
4. If rejected, appellant may re-appeal ONCE (with new evidence)
5. Final decision by jury chair on re-appeal is binding
"""
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone


# ── CONSTANTS ──────────────────────────────────────────────────────────────────
APPEAL_FEE_KES = 2000       # KES 2,000 appeal submission fee (refundable if appeal succeeds)
REAPPEAL_FEE_KES = 4000     # KES 4,000 re-appeal fee
REAPPEAL_WINDOW_MINUTES = 10  # Re-appeal must be filed within 10 minutes of decision
RESPONSE_WINDOW_MINUTES = 30  # Respondent has 30 minutes to submit a response
FILING_WINDOW_MINUTES = 30    # Appeal must be filed within 30 minutes after end of match


class AppealStatus(models.TextChoices):
    DRAFT              = "draft",              "Draft"
    SUBMITTED          = "submitted",          "Submitted — Awaiting Response"
    RESPONSE_RECEIVED  = "response_received",  "Response Received — Awaiting Jury"
    UNDER_REVIEW       = "under_review",       "Under Jury Review"
    DECIDED            = "decided",            "Decision Made"
    CLOSED             = "closed",             "Closed"


class AppealDecision(models.TextChoices):
    SUCCESSFUL     = "successful",     "Appeal Successful"
    REJECTED       = "rejected",       "Appeal Rejected"
    MORE_INFO      = "more_info",      "More Information Required"


class EvidenceType(models.TextChoices):
    IMAGE    = "image",    "Image / Photo"
    DOCUMENT = "document", "Document (PDF / Word)"
    VIDEO    = "video",    "Video Evidence"
    OTHER    = "other",    "Other"


class FeeStatus(models.TextChoices):
    UNPAID   = "unpaid",   "Unpaid"
    PENDING  = "pending",  "Payment Pending Verification"
    VERIFIED = "verified", "Payment Verified"
    REFUNDED = "refunded", "Refunded"


# ══════════════════════════════════════════════════════════════════════════════
#  APPEAL
# ══════════════════════════════════════════════════════════════════════════════

class Appeal(models.Model):
    """
    An appeal submitted by a Team Manager against another team or a match
    decision. Must include at least one piece of evidence and fee payment
    before submission.
    """
    # ── Parties ────────────────────────────────────────────────────────────
    appellant_team = models.ForeignKey(
        "teams.Team", on_delete=models.CASCADE,
        related_name="appeals_filed",
        help_text="Team filing the appeal"
    )
    appellant_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="appeals_submitted",
        help_text="Team Manager who submitted the appeal"
    )
    respondent_team = models.ForeignKey(
        "teams.Team", on_delete=models.CASCADE,
        related_name="appeals_received",
        help_text="Team the appeal is filed against"
    )
    # Optional link to a specific match
    match = models.ForeignKey(
        "competitions.Fixture", on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="appeals",
        help_text="Match this appeal relates to (optional)"
    )
    competition = models.ForeignKey(
        "competitions.Competition", on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="appeals",
        help_text="Competition this appeal relates to"
    )

    # ── Appeal content ─────────────────────────────────────────────────────
    subject    = models.CharField(max_length=300, help_text="Brief summary of the appeal")
    details    = models.TextField(help_text="Full description of the grievance and grounds for appeal")

    # ── Status & workflow ──────────────────────────────────────────────────
    status = models.CharField(
        max_length=30, choices=AppealStatus.choices,
        default=AppealStatus.DRAFT
    )

    # ── Fee ────────────────────────────────────────────────────────────────
    fee_amount  = models.DecimalField(
        max_digits=10, decimal_places=2, default=APPEAL_FEE_KES,
        help_text="Appeal fee in KES"
    )
    fee_status  = models.CharField(
        max_length=20, choices=FeeStatus.choices,
        default=FeeStatus.UNPAID
    )
    fee_reference = models.CharField(
        max_length=100, blank=True,
        help_text="M-Pesa or receipt reference for fee payment"
    )
    fee_verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="appeal_fees_verified"
    )
    fee_verified_at = models.DateTimeField(null=True, blank=True)

    # ── Re-appeal tracking ─────────────────────────────────────────────────
    is_reappeal = models.BooleanField(default=False, help_text="This is a re-appeal of a previously rejected appeal")
    original_appeal = models.ForeignKey(
        "self", on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="reappeals",
        help_text="Original appeal this re-appeal is based on"
    )

    # ── Deadlines ──────────────────────────────────────────────────────────
    response_deadline = models.DateTimeField(
        null=True, blank=True,
        help_text="Deadline for respondent team to submit a response"
    )
    reappeal_deadline = models.DateTimeField(
        null=True, blank=True,
        help_text="Deadline to file a re-appeal (10 minutes after decision)"
    )

    # ── Timestamps ─────────────────────────────────────────────────────────
    created_at  = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Appeal"
        verbose_name_plural = "Appeals"

    def __str__(self):
        return f"Appeal #{self.pk}: {self.subject} ({self.get_status_display()})"

    # ── Computed properties ────────────────────────────────────────────────
    @property
    def has_evidence(self):
        """At least one evidence file must be attached."""
        return self.evidence_files.exists()

    @property
    def fee_is_paid(self):
        return self.fee_status in (FeeStatus.VERIFIED, FeeStatus.PENDING)

    @property
    def can_submit(self):
        """Appeal can only be submitted with evidence + paid fee."""
        return self.has_evidence and self.fee_status == FeeStatus.VERIFIED

    @property
    def filing_window_ok(self):
        """
        When linked to a match, the appeal must be filed within 30 minutes
        after the match ends.  For live matches the window hasn't closed yet.
        Returns True if no match is linked or the window is still open.
        """
        if not self.match:
            return True
        from competitions.models import FixtureStatus
        if self.match.status == FixtureStatus.LIVE:
            return True  # match still running
        # For completed / other statuses, use kickoff + 90 min as estimated end
        kickoff_dt = getattr(self.match, 'kickoff_datetime', None)
        if not kickoff_dt:
            return True  # no kickoff time recorded, allow filing
        if timezone.is_naive(kickoff_dt):
            kickoff_dt = timezone.make_aware(kickoff_dt)
        estimated_end = kickoff_dt + timezone.timedelta(minutes=90)
        filing_deadline = estimated_end + timezone.timedelta(minutes=FILING_WINDOW_MINUTES)
        return timezone.now() <= filing_deadline

    def resolve_respondent_from_match(self):
        """
        If a match is linked, automatically set the respondent_team to the
        opponent (the other team in the fixture).
        """
        if not self.match or not self.appellant_team_id:
            return
        fixture = self.match
        if fixture.home_team_id == self.appellant_team_id:
            self.respondent_team = fixture.away_team
        elif fixture.away_team_id == self.appellant_team_id:
            self.respondent_team = fixture.home_team

    @property
    def has_response(self):
        try:
            return self.response is not None
        except AppealResponse.DoesNotExist:
            return False

    @property
    def has_decision(self):
        return self.decisions.exists()

    @property
    def latest_decision(self):
        return self.decisions.order_by("-created_at").first()

    @property
    def can_reappeal(self):
        """
        A team can re-appeal ONCE if the decision was 'rejected'.
        Cannot re-appeal a re-appeal.
        Must be filed within 10 minutes of the decision being published.
        """
        if self.is_reappeal:
            return False
        decision = self.latest_decision
        if not decision:
            return False
        if decision.outcome != AppealDecision.REJECTED:
            return False
        if not decision.is_published or not decision.published_at:
            return False
        # Check 10-minute window
        window_end = decision.published_at + timezone.timedelta(minutes=REAPPEAL_WINDOW_MINUTES)
        if timezone.now() > window_end:
            return False
        # Check no re-appeal already exists
        return not self.reappeals.exists()

    @property
    def response_overdue(self):
        if not self.response_deadline:
            return False
        return timezone.now() > self.response_deadline and not self.has_response

    def clean(self):
        super().clean()
        # Cannot appeal your own team
        if self.appellant_team_id and self.respondent_team_id:
            if self.appellant_team_id == self.respondent_team_id:
                raise ValidationError("A team cannot appeal against itself.")
        # Re-appeal validation
        if self.is_reappeal and not self.original_appeal:
            raise ValidationError("A re-appeal must reference the original appeal.")
        if self.is_reappeal and self.original_appeal:
            if self.original_appeal.is_reappeal:
                raise ValidationError("Cannot re-appeal a re-appeal. Only one re-appeal is allowed.")

    def _calculate_response_deadline(self):
        """
        Calculate the response deadline based on the related match status.

        Rules:
        - If the match is LIVE (ongoing): deadline = 30 minutes after match ends.
          Since the exact end time is unknown, we estimate 90 minutes from kickoff
          plus 30 minutes → 120 minutes from kickoff_datetime. If kickoff has
          already passed more than 120 min ago, deadline = now + 30 min.
        - If the match is NOT ongoing (completed, pending, etc.) or no match is
          linked: deadline = 30 minutes after the appeal is submitted.
        """
        from competitions.models import FixtureStatus
        now = timezone.now()

        if self.match:
            if self.match.status == FixtureStatus.LIVE:
                # Match is ongoing — estimate end time as kickoff + 90 min, then add 30 min
                kickoff_dt = self.match.kickoff_datetime
                if kickoff_dt:
                    # Make naive datetime aware if needed
                    if timezone.is_naive(kickoff_dt):
                        kickoff_dt = timezone.make_aware(kickoff_dt)
                    estimated_end = kickoff_dt + timezone.timedelta(minutes=90)
                    deadline = estimated_end + timezone.timedelta(minutes=30)
                    # If the estimated deadline is already past, give 30 min from now
                    if deadline < now:
                        deadline = now + timezone.timedelta(minutes=30)
                    return deadline

        # Default: 30 minutes from submission
        return now + timezone.timedelta(minutes=30)

    def submit(self):
        """Transition from draft to submitted."""
        if not self.can_submit:
            raise ValidationError(
                "Cannot submit: ensure evidence is attached and fee is verified."
            )
        self.status = AppealStatus.SUBMITTED
        self.submitted_at = timezone.now()
        # 30-minute response deadline based on match status
        self.response_deadline = self._calculate_response_deadline()
        self.save()


# ══════════════════════════════════════════════════════════════════════════════
#  APPEAL EVIDENCE
# ══════════════════════════════════════════════════════════════════════════════

class AppealEvidence(models.Model):
    """
    Evidence file attached to an appeal.
    At least ONE evidence file is mandatory for submission.
    """
    appeal = models.ForeignKey(
        Appeal, on_delete=models.CASCADE, related_name="evidence_files"
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    evidence_type = models.CharField(
        max_length=20, choices=EvidenceType.choices, default=EvidenceType.DOCUMENT
    )
    file = models.FileField(
        upload_to="appeals/evidence/%Y/%m/",
        help_text="Upload evidence (images, documents, videos)"
    )
    title = models.CharField(max_length=200, help_text="Brief description of this evidence")
    description = models.TextField(blank=True, help_text="Detailed description of this evidence")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]
        verbose_name = "Appeal Evidence"
        verbose_name_plural = "Appeal Evidence Files"

    def __str__(self):
        return f"{self.title} ({self.get_evidence_type_display()})"


# ══════════════════════════════════════════════════════════════════════════════
#  APPEAL RESPONSE (from respondent team)
# ══════════════════════════════════════════════════════════════════════════════

class AppealResponse(models.Model):
    """
    Response from the respondent team's manager. Must include evidence.
    """
    appeal = models.OneToOneField(
        Appeal, on_delete=models.CASCADE, related_name="response"
    )
    respondent_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="appeal_responses",
        help_text="Team Manager who submitted the response"
    )
    statement = models.TextField(help_text="Response statement addressing the appeal")
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Appeal Response"

    def __str__(self):
        return f"Response to Appeal #{self.appeal_id}"

    @property
    def has_evidence(self):
        return self.evidence_files.exists()


class ResponseEvidence(models.Model):
    """Evidence attached to a response."""
    response = models.ForeignKey(
        AppealResponse, on_delete=models.CASCADE, related_name="evidence_files"
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    evidence_type = models.CharField(
        max_length=20, choices=EvidenceType.choices, default=EvidenceType.DOCUMENT
    )
    file = models.FileField(
        upload_to="appeals/responses/%Y/%m/",
        help_text="Upload evidence for the response"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]
        verbose_name = "Response Evidence"
        verbose_name_plural = "Response Evidence Files"

    def __str__(self):
        return f"{self.title} ({self.get_evidence_type_display()})"


# ══════════════════════════════════════════════════════════════════════════════
#  JURY DECISION
# ══════════════════════════════════════════════════════════════════════════════

class JuryDecision(models.Model):
    """
    Decision by the Chair of the Jury. Must include reasoning and evidence.
    """
    appeal = models.ForeignKey(
        Appeal, on_delete=models.CASCADE, related_name="decisions"
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="jury_decisions",
        help_text="Chair of the Jury who made this decision"
    )
    outcome = models.CharField(
        max_length=20, choices=AppealDecision.choices,
        help_text="Outcome of the appeal"
    )
    reasoning = models.TextField(
        help_text="Detailed reasoning for the decision — MANDATORY"
    )
    sanctions = models.TextField(
        blank=True,
        help_text="Any sanctions or remedies imposed"
    )
    is_published = models.BooleanField(
        default=False,
        help_text="When published, both teams can see the decision"
    )
    published_at = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Jury Decision"

    def __str__(self):
        return f"Decision on Appeal #{self.appeal_id}: {self.get_outcome_display()}"

    @property
    def has_evidence(self):
        return self.evidence_files.exists()

    def publish(self):
        """Mark the decision as published, visible to both teams."""
        self.is_published = True
        self.published_at = timezone.now()
        # Update appeal status
        if self.outcome == AppealDecision.MORE_INFO:
            self.appeal.status = AppealStatus.SUBMITTED
        else:
            self.appeal.status = AppealStatus.DECIDED
        # If appeal is successful, fee is refundable
        if self.outcome == AppealDecision.SUCCESSFUL:
            self.appeal.fee_status = FeeStatus.REFUNDED
        # If rejected and not a re-appeal, set 10-minute re-appeal window
        if self.outcome == AppealDecision.REJECTED and not self.appeal.is_reappeal:
            self.appeal.reappeal_deadline = timezone.now() + timezone.timedelta(minutes=REAPPEAL_WINDOW_MINUTES)
        self.appeal.save()
        self.save()


class DecisionEvidence(models.Model):
    """Evidence attached to a jury decision."""
    decision = models.ForeignKey(
        JuryDecision, on_delete=models.CASCADE, related_name="evidence_files"
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    evidence_type = models.CharField(
        max_length=20, choices=EvidenceType.choices, default=EvidenceType.DOCUMENT
    )
    file = models.FileField(
        upload_to="appeals/decisions/%Y/%m/",
        help_text="Upload evidence supporting the decision"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]
        verbose_name = "Decision Evidence"
        verbose_name_plural = "Decision Evidence Files"

    def __str__(self):
        return f"{self.title} ({self.get_evidence_type_display()})"


# ══════════════════════════════════════════════════════════════════════════════
#  HEARING SCHEDULE
# ══════════════════════════════════════════════════════════════════════════════

class HearingSchedule(models.Model):
    """
    Hearing date/time scheduled by the Chair of the Jury for an appeal.
    Multiple hearings may be scheduled (e.g. adjournment / rescheduling).
    """
    appeal = models.ForeignKey(
        Appeal, on_delete=models.CASCADE, related_name="hearings",
        help_text="Appeal this hearing is for"
    )
    hearing_date = models.DateField(help_text="Date of the hearing")
    hearing_time = models.TimeField(help_text="Time of the hearing")
    location = models.CharField(
        max_length=300, blank=True,
        help_text="Hearing venue or virtual meeting link"
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional notes or agenda for the hearing"
    )
    scheduled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="hearings_scheduled",
        help_text="Jury Chair who scheduled this hearing"
    )
    is_cancelled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-hearing_date", "-hearing_time"]
        verbose_name = "Hearing Schedule"
        verbose_name_plural = "Hearing Schedules"

    def __str__(self):
        return f"Hearing for Appeal #{self.appeal_id} on {self.hearing_date} at {self.hearing_time}"

    @property
    def hearing_datetime(self):
        from datetime import datetime
        return datetime.combine(self.hearing_date, self.hearing_time)

    @property
    def is_upcoming(self):
        from datetime import datetime
        return datetime.combine(self.hearing_date, self.hearing_time) > timezone.now().replace(tzinfo=None)

    @property
    def is_past(self):
        return not self.is_upcoming
