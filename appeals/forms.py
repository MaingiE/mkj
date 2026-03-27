"""
MKJ SUPA CUP Appeals - Forms for appeal submission, response, and jury decisions
"""
from django import forms
from django.core.exceptions import ValidationError
from .models import (
    Appeal, AppealEvidence, AppealResponse, ResponseEvidence,
    JuryDecision, DecisionEvidence, HearingSchedule,
    EvidenceType, FeeStatus, AppealDecision,
    APPEAL_FEE_KES, REAPPEAL_FEE_KES,
)


# ══════════════════════════════════════════════════════════════════════════════
#  APPEAL FORMS
# ══════════════════════════════════════════════════════════════════════════════

class AppealForm(forms.ModelForm):
    """Form for creating / editing an appeal (Team Manager)."""

    class Meta:
        model = Appeal
        fields = ["respondent_team", "match", "competition", "subject", "details"]
        widgets = {
            "subject": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Brief summary of the appeal",
            }),
            "details": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 6,
                "placeholder": "Full description of your grievance and grounds for appeal...",
            }),
            "respondent_team": forms.Select(attrs={"class": "form-select"}),
            "match": forms.Select(attrs={"class": "form-select"}),
            "competition": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, appellant_team=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.appellant_team = appellant_team
        # Exclude appellant team from respondent choices
        if appellant_team:
            from teams.models import Team
            self.fields["respondent_team"].queryset = Team.objects.exclude(pk=appellant_team.pk)
        self.fields["match"].required = False
        self.fields["competition"].required = False
        # Respondent is auto-determined from match - hide but keep for fallback
        self.fields["respondent_team"].required = False
        self.fields["respondent_team"].widget = forms.HiddenInput()

    def clean(self):
        cleaned = super().clean()
        match = cleaned.get("match")
        respondent = cleaned.get("respondent_team")
        # Auto-resolve respondent from the selected match
        if match and self.appellant_team:
            if match.home_team_id == self.appellant_team.pk:
                cleaned["respondent_team"] = match.away_team
            elif match.away_team_id == self.appellant_team.pk:
                cleaned["respondent_team"] = match.home_team
            else:
                raise ValidationError("Your team is not involved in the selected match.")
        respondent = cleaned.get("respondent_team")
        if not respondent:
            raise ValidationError("A match must be selected so the opponent (respondent) is determined.")
        if self.appellant_team and respondent and respondent == self.appellant_team:
            raise ValidationError("You cannot file an appeal against your own team.")
        # Validate 30-min filing window
        if match:
            from .models import FILING_WINDOW_MINUTES
            from competitions.models import FixtureStatus
            from django.utils import timezone as tz
            if match.status != FixtureStatus.LIVE:
                kickoff_dt = getattr(match, 'kickoff_datetime', None)
                if kickoff_dt:
                    if tz.is_naive(kickoff_dt):
                        kickoff_dt = tz.make_aware(kickoff_dt)
                    estimated_end = kickoff_dt + tz.timedelta(minutes=90)
                    filing_deadline = estimated_end + tz.timedelta(minutes=FILING_WINDOW_MINUTES)
                    if tz.now() > filing_deadline:
                        raise ValidationError(
                            f"Appeals must be filed within {FILING_WINDOW_MINUTES} minutes "
                            f"after the end of the match. The window has expired."
                        )
        return cleaned


class AppealFeeForm(forms.Form):
    """Form for submitting fee payment details."""
    fee_reference = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "M-Pesa confirmation code or receipt reference",
        }),
        help_text=(
            f"Appeal fee: KES {APPEAL_FEE_KES:,} (refundable if appeal succeeds). "
            f"Re-appeal fee: KES {REAPPEAL_FEE_KES:,}. Enter your payment reference."
        ),
    )


class AppealEvidenceForm(forms.ModelForm):
    """Form for uploading evidence to an appeal."""

    class Meta:
        model = AppealEvidence
        fields = ["title", "evidence_type", "file", "description"]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "e.g. Match video clip, Referee report photo",
            }),
            "evidence_type": forms.Select(attrs={"class": "form-select"}),
            "file": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Describe what this evidence shows...",
            }),
        }


# ══════════════════════════════════════════════════════════════════════════════
#  RESPONSE FORMS
# ══════════════════════════════════════════════════════════════════════════════

class AppealResponseForm(forms.ModelForm):
    """Form for respondent team to submit a response."""

    class Meta:
        model = AppealResponse
        fields = ["statement"]
        widgets = {
            "statement": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 6,
                "placeholder": "Your response statement addressing the appeal...",
            }),
        }


class ResponseEvidenceForm(forms.ModelForm):
    """Form for uploading evidence to a response."""

    class Meta:
        model = ResponseEvidence
        fields = ["title", "evidence_type", "file", "description"]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Evidence title",
            }),
            "evidence_type": forms.Select(attrs={"class": "form-select"}),
            "file": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Describe what this evidence shows...",
            }),
        }


# ══════════════════════════════════════════════════════════════════════════════
#  JURY DECISION FORMS
# ══════════════════════════════════════════════════════════════════════════════

class JuryDecisionForm(forms.ModelForm):
    """Form for Chair of the Jury to make a decision."""

    class Meta:
        model = JuryDecision
        fields = ["outcome", "reasoning", "sanctions"]
        widgets = {
            "outcome": forms.Select(attrs={"class": "form-select"}),
            "reasoning": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 6,
                "placeholder": "Detailed reasoning for your decision (MANDATORY)...",
            }),
            "sanctions": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Any sanctions or remedies to impose (optional)...",
            }),
        }

    def clean_reasoning(self):
        reasoning = self.cleaned_data.get("reasoning", "").strip()
        if not reasoning:
            raise ValidationError("Reasoning is mandatory for all jury decisions.")
        if len(reasoning) < 50:
            raise ValidationError("Please provide more detailed reasoning (at least 50 characters).")
        return reasoning


class DecisionEvidenceForm(forms.ModelForm):
    """Form for uploading evidence to a jury decision."""

    class Meta:
        model = DecisionEvidence
        fields = ["title", "evidence_type", "file", "description"]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Evidence title",
            }),
            "evidence_type": forms.Select(attrs={"class": "form-select"}),
            "file": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
            }),
        }


# ══════════════════════════════════════════════════════════════════════════════
#  FEE VERIFICATION FORM (Admin / Treasurer)
# ══════════════════════════════════════════════════════════════════════════════

class FeeVerificationForm(forms.Form):
    """Form for admin/treasurer to verify appeal fee payment."""
    action = forms.ChoiceField(
        choices=[
            ("verify", "Verify Payment"),
            ("reject", "Reject Payment"),
            ("refund", "Process Refund"),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 2,
            "placeholder": "Optional notes about this fee action...",
        }),
    )


# ══════════════════════════════════════════════════════════════════════════════
#  HEARING SCHEDULE FORM (Chair of the Jury)
# ══════════════════════════════════════════════════════════════════════════════

class HearingScheduleForm(forms.ModelForm):
    """Form for the Jury Chair to schedule a hearing date/time for an appeal."""

    class Meta:
        model = HearingSchedule
        fields = ["hearing_date", "hearing_time", "location", "notes"]
        widgets = {
            "hearing_date": forms.DateInput(attrs={
                "class": "form-control",
                "type": "date",
            }),
            "hearing_time": forms.TimeInput(attrs={
                "class": "form-control",
                "type": "time",
            }),
            "location": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "e.g. MKJ SUPA CUP Office, Nairobi or Zoom meeting link",
            }),
            "notes": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Additional hearing notes or agenda items...",
            }),
        }

    def clean_hearing_date(self):
        from django.utils import timezone
        hearing_date = self.cleaned_data.get("hearing_date")
        if hearing_date and hearing_date < timezone.now().date():
            raise ValidationError("Hearing date cannot be in the past.")
        return hearing_date
