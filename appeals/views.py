"""
MKJ SUPA CUP Appeals — Views for the Jury & Appeals Management System

Roles:
- Team Manager: Submit appeals, upload evidence, pay fees, re-appeal
- Respondent Team Manager: Submit response with evidence
- Chair of the Jury: Review appeals, make decisions, publish
- Admin/Treasurer: Verify fee payments
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, Http404
from django.utils import timezone
from django.db.models import Q

from accounts.models import UserRole
from teams.models import Team
from .models import (
    Appeal, AppealEvidence, AppealResponse, ResponseEvidence,
    JuryDecision, DecisionEvidence, HearingSchedule,
    AppealStatus, AppealDecision, FeeStatus,
    APPEAL_FEE_KES, REAPPEAL_FEE_KES, REAPPEAL_WINDOW_MINUTES,
)
from .forms import (
    AppealForm, AppealEvidenceForm, AppealFeeForm,
    AppealResponseForm, ResponseEvidenceForm,
    JuryDecisionForm, DecisionEvidenceForm,
    FeeVerificationForm, HearingScheduleForm,
)


# ── Role decorators ────────────────────────────────────────────────────────────
def team_manager_required(view_func):
    """Only allow team_manager role."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("web_login")
        if request.user.role != UserRole.TEAM_MANAGER:
            messages.error(request, "Only Team Managers can access this page.")
            return redirect("dashboard")
        return view_func(request, *args, **kwargs)
    return wrapper


def jury_chair_required(view_func):
    """Only allow jury_chair role."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("web_login")
        if request.user.role != UserRole.JURY_CHAIR and not request.user.is_admin:
            messages.error(request, "Only the Chair of the Jury can access this page.")
            return redirect("dashboard")
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_or_treasurer_required(view_func):
    """Allow admin or treasurer."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("web_login")
        if not (request.user.is_admin or request.user.is_treasurer):
            messages.error(request, "Only Admins or Treasurers can verify fees.")
            return redirect("dashboard")
        return view_func(request, *args, **kwargs)
    return wrapper


# ══════════════════════════════════════════════════════════════════════════════
#  APPEAL LIST VIEWS
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def appeals_list_view(request):
    """
    List appeals based on user role:
    - Team Manager: sees own team's filed + received appeals
    - Jury Chair: sees all submitted appeals
    - Admin: sees everything
    """
    user = request.user

    if user.is_admin or user.role == UserRole.JURY_CHAIR or user.role == UserRole.SECRETARY_GENERAL:
        appeals = Appeal.objects.all()
    elif user.role == UserRole.TEAM_MANAGER:
        managed_teams = Team.objects.filter(manager=user)
        appeals = Appeal.objects.filter(
            Q(appellant_team__in=managed_teams) |
            Q(respondent_team__in=managed_teams)
        )
    elif user.is_treasurer:
        appeals = Appeal.objects.all()
    else:
        appeals = Appeal.objects.none()

    # Filters
    status_filter = request.GET.get("status", "")
    if status_filter:
        appeals = appeals.filter(status=status_filter)

    context = {
        "appeals": appeals.select_related(
            "appellant_team", "respondent_team", "appellant_user", "competition"
        ),
        "status_choices": AppealStatus.choices,
        "current_status": status_filter,
        "user_role": user.role,
    }
    return render(request, "appeals/appeals_list.html", context)


# ══════════════════════════════════════════════════════════════════════════════
#  APPEAL DETAIL
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def appeal_detail_view(request, pk):
    """View full appeal details with evidence, response, and decisions."""
    appeal = get_object_or_404(Appeal, pk=pk)
    user = request.user

    # Access control
    managed_teams = Team.objects.filter(manager=user)
    is_appellant = appeal.appellant_team in list(managed_teams)
    is_respondent = appeal.respondent_team in list(managed_teams)
    is_jury = user.role == UserRole.JURY_CHAIR
    is_admin = user.is_admin
    is_treasurer = user.is_treasurer

    if not (is_appellant or is_respondent or is_jury or is_admin or is_treasurer):
        raise Http404("Appeal not found.")

    evidence = appeal.evidence_files.all()
    response = None
    response_evidence = []
    try:
        response = appeal.response
        response_evidence = response.evidence_files.all()
    except AppealResponse.DoesNotExist:
        pass

    decisions = appeal.decisions.all()
    hearings = appeal.hearings.filter(is_cancelled=False)

    context = {
        "appeal": appeal,
        "evidence": evidence,
        "response": response,
        "response_evidence": response_evidence,
        "decisions": decisions,
        "hearings": hearings,
        "is_appellant": is_appellant,
        "is_respondent": is_respondent,
        "is_jury": is_jury,
        "is_admin": is_admin,
        "is_treasurer": is_treasurer,
        "can_respond": is_respondent and appeal.status == AppealStatus.SUBMITTED and not appeal.has_response,
        "can_decide": is_jury and appeal.status in (AppealStatus.RESPONSE_RECEIVED, AppealStatus.UNDER_REVIEW, AppealStatus.SUBMITTED),
        "can_schedule_hearing": is_jury and appeal.status not in (AppealStatus.DRAFT, AppealStatus.CLOSED),
        "can_reappeal": is_appellant and appeal.can_reappeal,
        "APPEAL_FEE": APPEAL_FEE_KES,
        "REAPPEAL_FEE": REAPPEAL_FEE_KES,
        "REAPPEAL_WINDOW_MINUTES": REAPPEAL_WINDOW_MINUTES,
    }
    return render(request, "appeals/appeal_detail.html", context)


# ══════════════════════════════════════════════════════════════════════════════
#  SUBMIT APPEAL (Team Manager)
# ══════════════════════════════════════════════════════════════════════════════

@team_manager_required
def submit_appeal_view(request):
    """Create a new appeal (draft). Evidence and fee added separately."""
    managed_teams = Team.objects.filter(manager=request.user)
    if not managed_teams.exists():
        messages.error(request, "You must manage a team to file an appeal.")
        return redirect("appeals_list")

    # Use first managed team as appellant
    appellant_team = managed_teams.first()

    if request.method == "POST":
        form = AppealForm(request.POST, appellant_team=appellant_team)
        if form.is_valid():
            appeal = form.save(commit=False)
            appeal.appellant_team = appellant_team
            appeal.appellant_user = request.user
            appeal.fee_amount = APPEAL_FEE_KES
            appeal.save()
            messages.success(request, "Appeal draft created. Now add evidence and pay the fee.")
            return redirect("appeal_detail", pk=appeal.pk)
    else:
        form = AppealForm(appellant_team=appellant_team)

    context = {
        "form": form,
        "appellant_team": appellant_team,
        "APPEAL_FEE": APPEAL_FEE_KES,
    }
    return render(request, "appeals/submit_appeal.html", context)


# ══════════════════════════════════════════════════════════════════════════════
#  UPLOAD EVIDENCE (Appellant)
# ══════════════════════════════════════════════════════════════════════════════

@team_manager_required
def upload_evidence_view(request, pk):
    """Upload evidence files to an appeal."""
    appeal = get_object_or_404(Appeal, pk=pk)

    # Only appellant can add evidence, and only in draft status
    managed_teams = Team.objects.filter(manager=request.user)
    if appeal.appellant_team not in list(managed_teams):
        messages.error(request, "Only the filing team can add evidence to this appeal.")
        return redirect("appeal_detail", pk=pk)

    if appeal.status not in (AppealStatus.DRAFT, AppealStatus.SUBMITTED):
        messages.error(request, "Evidence can only be added to draft or submitted appeals.")
        return redirect("appeal_detail", pk=pk)

    if request.method == "POST":
        form = AppealEvidenceForm(request.POST, request.FILES)
        if form.is_valid():
            evidence = form.save(commit=False)
            evidence.appeal = appeal
            evidence.uploaded_by = request.user
            evidence.save()
            messages.success(request, f"Evidence '{evidence.title}' uploaded successfully.")
            return redirect("appeal_detail", pk=pk)
    else:
        form = AppealEvidenceForm()

    context = {
        "form": form,
        "appeal": appeal,
    }
    return render(request, "appeals/upload_evidence.html", context)


# ══════════════════════════════════════════════════════════════════════════════
#  PAY APPEAL FEE
# ══════════════════════════════════════════════════════════════════════════════

@team_manager_required
def pay_fee_view(request, pk):
    """Submit fee payment reference."""
    appeal = get_object_or_404(Appeal, pk=pk)

    managed_teams = Team.objects.filter(manager=request.user)
    if appeal.appellant_team not in list(managed_teams):
        messages.error(request, "Only the filing team can pay the fee.")
        return redirect("appeal_detail", pk=pk)

    if appeal.fee_status in (FeeStatus.VERIFIED, FeeStatus.PENDING):
        messages.info(request, "Fee payment has already been submitted.")
        return redirect("appeal_detail", pk=pk)

    if request.method == "POST":
        form = AppealFeeForm(request.POST)
        if form.is_valid():
            appeal.fee_reference = form.cleaned_data["fee_reference"]
            appeal.fee_status = FeeStatus.PENDING
            appeal.save()
            messages.success(request, "Fee payment reference submitted. Awaiting verification.")
            return redirect("appeal_detail", pk=pk)
    else:
        form = AppealFeeForm()

    context = {
        "form": form,
        "appeal": appeal,
        "APPEAL_FEE": APPEAL_FEE_KES,
    }
    return render(request, "appeals/pay_fee.html", context)


# ══════════════════════════════════════════════════════════════════════════════
#  FINALIZE / SUBMIT APPEAL (change from draft to submitted)
# ══════════════════════════════════════════════════════════════════════════════

@team_manager_required
def finalize_appeal_view(request, pk):
    """Submit the appeal (move from draft to submitted)."""
    appeal = get_object_or_404(Appeal, pk=pk)

    managed_teams = Team.objects.filter(manager=request.user)
    if appeal.appellant_team not in list(managed_teams):
        messages.error(request, "Only the filing team can submit this appeal.")
        return redirect("appeal_detail", pk=pk)

    if appeal.status != AppealStatus.DRAFT:
        messages.warning(request, "This appeal has already been submitted.")
        return redirect("appeal_detail", pk=pk)

    # Validate: evidence + fee
    if not appeal.has_evidence:
        messages.error(request, "You must upload at least one evidence file before submitting.")
        return redirect("appeal_detail", pk=pk)

    if appeal.fee_status != FeeStatus.VERIFIED:
        messages.error(request, "Your fee payment must be verified before you can submit the appeal.")
        return redirect("appeal_detail", pk=pk)

    if request.method == "POST":
        appeal.status = AppealStatus.SUBMITTED
        appeal.submitted_at = timezone.now()
        # 30-minute response deadline based on match status
        appeal.response_deadline = appeal._calculate_response_deadline()
        appeal.save()

        # Determine deadline description for user feedback
        if appeal.match and hasattr(appeal.match, 'status') and appeal.match.status == 'live':
            deadline_msg = "The respondent team must respond within 30 minutes after the match ends."
        else:
            deadline_msg = "The respondent team must respond within 30 minutes."

        # Send email notification to respondent team
        from .notifications import notify_appeal_submitted
        notify_appeal_submitted(appeal)

        messages.success(request, f"Appeal submitted successfully! {deadline_msg}")
        return redirect("appeal_detail", pk=pk)

    return render(request, "appeals/finalize_appeal.html", {"appeal": appeal})


# ══════════════════════════════════════════════════════════════════════════════
#  APPEAL RESPONSE (Respondent Team Manager)
# ══════════════════════════════════════════════════════════════════════════════

@team_manager_required
def submit_response_view(request, pk):
    """Respondent team submits their response."""
    appeal = get_object_or_404(Appeal, pk=pk)

    managed_teams = Team.objects.filter(manager=request.user)
    if appeal.respondent_team not in list(managed_teams):
        messages.error(request, "Only the respondent team can submit a response.")
        return redirect("appeal_detail", pk=pk)

    if appeal.status != AppealStatus.SUBMITTED:
        messages.error(request, "This appeal is not awaiting a response.")
        return redirect("appeal_detail", pk=pk)

    if appeal.has_response:
        messages.info(request, "A response has already been submitted for this appeal.")
        return redirect("appeal_detail", pk=pk)

    if request.method == "POST":
        form = AppealResponseForm(request.POST)
        if form.is_valid():
            response = form.save(commit=False)
            response.appeal = appeal
            response.respondent_user = request.user
            response.save()

            # Update appeal status
            appeal.status = AppealStatus.RESPONSE_RECEIVED
            appeal.save()

            # Notify appellant that a response was received
            from .notifications import notify_response_submitted
            notify_response_submitted(appeal)

            messages.success(request, "Response submitted. Now upload supporting evidence.")
            return redirect("upload_response_evidence", pk=appeal.pk)
    else:
        form = AppealResponseForm()

    context = {
        "form": form,
        "appeal": appeal,
    }
    return render(request, "appeals/submit_response.html", context)


@team_manager_required
def upload_response_evidence_view(request, pk):
    """Upload evidence for the response."""
    appeal = get_object_or_404(Appeal, pk=pk)

    if not appeal.has_response:
        messages.error(request, "Submit a response first before uploading evidence.")
        return redirect("appeal_detail", pk=pk)

    managed_teams = Team.objects.filter(manager=request.user)
    if appeal.respondent_team not in list(managed_teams):
        messages.error(request, "Only the respondent team can add response evidence.")
        return redirect("appeal_detail", pk=pk)

    response_obj = appeal.response

    if request.method == "POST":
        form = ResponseEvidenceForm(request.POST, request.FILES)
        if form.is_valid():
            evidence = form.save(commit=False)
            evidence.response = response_obj
            evidence.uploaded_by = request.user
            evidence.save()
            messages.success(request, f"Evidence '{evidence.title}' uploaded.")
            return redirect("appeal_detail", pk=pk)
    else:
        form = ResponseEvidenceForm()

    context = {
        "form": form,
        "appeal": appeal,
        "response": response_obj,
    }
    return render(request, "appeals/upload_response_evidence.html", context)


# ══════════════════════════════════════════════════════════════════════════════
#  JURY DECISION (Chair of the Jury)
# ══════════════════════════════════════════════════════════════════════════════

@jury_chair_required
def jury_decision_view(request, pk):
    """Chair of the Jury makes a decision on an appeal."""
    appeal = get_object_or_404(Appeal, pk=pk)

    if appeal.status not in (AppealStatus.SUBMITTED, AppealStatus.RESPONSE_RECEIVED, AppealStatus.UNDER_REVIEW):
        messages.error(request, "This appeal is not ready for a jury decision.")
        return redirect("appeal_detail", pk=pk)

    # Mark as under review
    if appeal.status != AppealStatus.UNDER_REVIEW:
        appeal.status = AppealStatus.UNDER_REVIEW
        appeal.save()

    if request.method == "POST":
        form = JuryDecisionForm(request.POST)
        if form.is_valid():
            decision = form.save(commit=False)
            decision.appeal = appeal
            decision.decided_by = request.user
            decision.save()
            messages.success(request, "Decision saved. Now upload supporting evidence, then publish.")
            return redirect("upload_decision_evidence", pk=appeal.pk, decision_pk=decision.pk)
    else:
        form = JuryDecisionForm()

    context = {
        "form": form,
        "appeal": appeal,
    }
    return render(request, "appeals/jury_decision.html", context)


@jury_chair_required
def upload_decision_evidence_view(request, pk, decision_pk):
    """Upload evidence for the jury decision."""
    appeal = get_object_or_404(Appeal, pk=pk)
    decision = get_object_or_404(JuryDecision, pk=decision_pk, appeal=appeal)

    if decision.is_published:
        messages.info(request, "This decision has already been published.")
        return redirect("appeal_detail", pk=pk)

    if request.method == "POST":
        form = DecisionEvidenceForm(request.POST, request.FILES)
        if form.is_valid():
            evidence = form.save(commit=False)
            evidence.decision = decision
            evidence.uploaded_by = request.user
            evidence.save()
            messages.success(request, f"Evidence '{evidence.title}' uploaded.")
            return redirect("upload_decision_evidence", pk=pk, decision_pk=decision_pk)
    else:
        form = DecisionEvidenceForm()

    context = {
        "form": form,
        "appeal": appeal,
        "decision": decision,
        "existing_evidence": decision.evidence_files.all(),
    }
    return render(request, "appeals/upload_decision_evidence.html", context)


@jury_chair_required
def publish_decision_view(request, pk, decision_pk):
    """Publish a jury decision — both teams can then see it."""
    appeal = get_object_or_404(Appeal, pk=pk)
    decision = get_object_or_404(JuryDecision, pk=decision_pk, appeal=appeal)

    if decision.is_published:
        messages.info(request, "This decision has already been published.")
        return redirect("appeal_detail", pk=pk)

    if not decision.has_evidence:
        messages.error(request, "You must upload at least one piece of evidence before publishing.")
        return redirect("upload_decision_evidence", pk=pk, decision_pk=decision_pk)

    if request.method == "POST":
        decision.publish()

        # Send email notification to both teams
        from .notifications import notify_decision_published
        notify_decision_published(decision)

        outcome_msg = "Decision published. Both teams have been notified by email."
        if decision.outcome == AppealDecision.SUCCESSFUL:
            outcome_msg += f" Appeal fee of KES {appeal.fee_amount:,.0f} will be refunded to the appellant."
        elif decision.outcome == AppealDecision.REJECTED and not appeal.is_reappeal:
            outcome_msg += f" The appellant has {REAPPEAL_WINDOW_MINUTES} minutes to file a re-appeal."

        messages.success(request, outcome_msg)
        return redirect("appeal_detail", pk=pk)

    context = {
        "appeal": appeal,
        "decision": decision,
    }
    return render(request, "appeals/publish_decision.html", context)


# ══════════════════════════════════════════════════════════════════════════════
#  HEARING SCHEDULE (Chair of the Jury)
# ══════════════════════════════════════════════════════════════════════════════

@jury_chair_required
def schedule_hearing_view(request, pk):
    """Chair of the Jury schedules a hearing date/time for an appeal."""
    appeal = get_object_or_404(Appeal, pk=pk)

    if appeal.status == AppealStatus.DRAFT:
        messages.error(request, "Cannot schedule a hearing for a draft appeal.")
        return redirect("appeal_detail", pk=pk)

    if appeal.status == AppealStatus.CLOSED:
        messages.error(request, "Cannot schedule a hearing for a closed appeal.")
        return redirect("appeal_detail", pk=pk)

    existing_hearings = appeal.hearings.filter(is_cancelled=False)

    if request.method == "POST":
        form = HearingScheduleForm(request.POST)
        if form.is_valid():
            hearing = form.save(commit=False)
            hearing.appeal = appeal
            hearing.scheduled_by = request.user
            hearing.save()

            # Send email notification to both teams
            from .notifications import notify_hearing_scheduled
            notify_hearing_scheduled(hearing)

            messages.success(
                request,
                f"Hearing scheduled for {hearing.hearing_date.strftime('%d %b %Y')} "
                f"at {hearing.hearing_time.strftime('%H:%M')}. Both teams have been notified."
            )
            return redirect("appeal_detail", pk=pk)
    else:
        form = HearingScheduleForm()

    context = {
        "form": form,
        "appeal": appeal,
        "existing_hearings": existing_hearings,
    }
    return render(request, "appeals/schedule_hearing.html", context)


@jury_chair_required
def cancel_hearing_view(request, pk, hearing_pk):
    """Cancel a scheduled hearing."""
    appeal = get_object_or_404(Appeal, pk=pk)
    hearing = get_object_or_404(HearingSchedule, pk=hearing_pk, appeal=appeal)

    if hearing.is_cancelled:
        messages.info(request, "This hearing has already been cancelled.")
        return redirect("appeal_detail", pk=pk)

    if request.method == "POST":
        hearing.is_cancelled = True
        hearing.save()

        # Notify both teams about cancellation
        from .notifications import notify_hearing_cancelled
        notify_hearing_cancelled(hearing)

        messages.success(request, "Hearing cancelled. Both teams have been notified.")
        return redirect("appeal_detail", pk=pk)

    context = {
        "appeal": appeal,
        "hearing": hearing,
    }
    return render(request, "appeals/cancel_hearing.html", context)


# ══════════════════════════════════════════════════════════════════════════════
#  RE-APPEAL (Team Manager — max 1)
# ══════════════════════════════════════════════════════════════════════════════

@team_manager_required
def reappeal_view(request, pk):
    """File a re-appeal on a rejected appeal (max 1 allowed, within 10 minutes)."""
    original = get_object_or_404(Appeal, pk=pk)

    managed_teams = Team.objects.filter(manager=request.user)
    if original.appellant_team not in list(managed_teams):
        messages.error(request, "Only the original filing team can re-appeal.")
        return redirect("appeal_detail", pk=pk)

    if not original.can_reappeal:
        # Check specific reason for better messaging
        decision = original.latest_decision
        if decision and decision.is_published and decision.published_at:
            window_end = decision.published_at + timezone.timedelta(minutes=REAPPEAL_WINDOW_MINUTES)
            if timezone.now() > window_end:
                messages.error(request, f"The {REAPPEAL_WINDOW_MINUTES}-minute re-appeal window has expired.")
                return redirect("appeal_detail", pk=pk)
        messages.error(request, "This appeal cannot be re-appealed. Either it was not rejected, is itself a re-appeal, or a re-appeal already exists.")
        return redirect("appeal_detail", pk=pk)

    appellant_team = original.appellant_team

    if request.method == "POST":
        form = AppealForm(request.POST, appellant_team=appellant_team)
        if form.is_valid():
            appeal = form.save(commit=False)
            appeal.appellant_team = appellant_team
            appeal.appellant_user = request.user
            appeal.fee_amount = REAPPEAL_FEE_KES
            appeal.is_reappeal = True
            appeal.original_appeal = original
            # Pre-fill respondent from original
            appeal.respondent_team = original.respondent_team
            appeal.competition = original.competition
            appeal.match = original.match
            appeal.save()

            # Notify both teams about re-appeal filing
            from .notifications import notify_reappeal_filed
            notify_reappeal_filed(appeal)

            messages.success(request, f"Re-appeal draft created. Fee is KES {REAPPEAL_FEE_KES:,}. Add new evidence and pay the fee.")
            return redirect("appeal_detail", pk=appeal.pk)
    else:
        form = AppealForm(
            appellant_team=appellant_team,
            initial={
                "respondent_team": original.respondent_team,
                "competition": original.competition,
                "match": original.match,
                "subject": f"Re-appeal: {original.subject}",
            }
        )

    # Calculate remaining time in re-appeal window
    decision = original.latest_decision
    remaining_seconds = 0
    if decision and decision.published_at:
        window_end = decision.published_at + timezone.timedelta(minutes=REAPPEAL_WINDOW_MINUTES)
        remaining_seconds = max(0, int((window_end - timezone.now()).total_seconds()))

    context = {
        "form": form,
        "original_appeal": original,
        "appellant_team": appellant_team,
        "APPEAL_FEE": REAPPEAL_FEE_KES,
        "remaining_seconds": remaining_seconds,
        "REAPPEAL_WINDOW_MINUTES": REAPPEAL_WINDOW_MINUTES,
    }
    return render(request, "appeals/reappeal.html", context)


# ══════════════════════════════════════════════════════════════════════════════
#  FEE VERIFICATION (Admin / Treasurer)
# ══════════════════════════════════════════════════════════════════════════════

@admin_or_treasurer_required
def verify_fee_view(request, pk):
    """Verify or reject a fee payment."""
    appeal = get_object_or_404(Appeal, pk=pk)

    if appeal.fee_status not in (FeeStatus.PENDING, FeeStatus.UNPAID):
        messages.info(request, f"Fee status is already: {appeal.get_fee_status_display()}")
        return redirect("appeal_detail", pk=pk)

    if request.method == "POST":
        form = FeeVerificationForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data["action"]
            if action == "verify":
                appeal.fee_status = FeeStatus.VERIFIED
                appeal.fee_verified_by = request.user
                appeal.fee_verified_at = timezone.now()
                appeal.save()
                # Notify appellant their fee was verified
                from .notifications import notify_fee_verified
                notify_fee_verified(appeal)
                messages.success(request, "Fee payment verified.")
            elif action == "reject":
                appeal.fee_status = FeeStatus.UNPAID
                appeal.fee_reference = ""
                appeal.save()
                # Notify appellant their fee was rejected
                from .notifications import notify_fee_rejected
                notify_fee_rejected(appeal)
                messages.warning(request, "Fee payment rejected. Team must resubmit.")
            elif action == "refund":
                appeal.fee_status = FeeStatus.REFUNDED
                appeal.save()
                # Notify appellant about refund
                from .notifications import notify_fee_refunded
                notify_fee_refunded(appeal)
                messages.info(request, "Fee marked as refunded.")
            return redirect("appeal_detail", pk=pk)
    else:
        form = FeeVerificationForm()

    context = {
        "form": form,
        "appeal": appeal,
    }
    return render(request, "appeals/verify_fee.html", context)


# ══════════════════════════════════════════════════════════════════════════════
#  JURY DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@jury_chair_required
def jury_dashboard_view(request):
    """Dashboard for the Chair of the Jury showing appeal statistics + competition overview."""
    from teams.models import Team, Player
    from competitions.models import Fixture
    from matches.models import MatchReport, MatchEvent, SquadSubmission

    # Appeal statistics
    total = Appeal.objects.count()
    pending_response = Appeal.objects.filter(status=AppealStatus.SUBMITTED).count()
    awaiting_decision = Appeal.objects.filter(
        status__in=[AppealStatus.RESPONSE_RECEIVED, AppealStatus.UNDER_REVIEW]
    ).count()
    decided = Appeal.objects.filter(status=AppealStatus.DECIDED).count()
    my_decisions = JuryDecision.objects.filter(decided_by=request.user).count()

    recent_appeals = Appeal.objects.exclude(
        status=AppealStatus.DRAFT
    ).select_related(
        "appellant_team", "respondent_team"
    ).order_by("-created_at")[:10]

    # Competition data summaries
    total_teams = Team.objects.filter(status="registered").count()
    total_players = Player.objects.filter(verification_status="verified").count()
    total_fixtures = Fixture.objects.count()
    completed_fixtures = Fixture.objects.filter(status="completed").count()
    total_reports = MatchReport.objects.count()
    total_squads = SquadSubmission.objects.count()
    card_types = ["yellow_card", "red_card", "second_yellow"]
    total_yellows = MatchEvent.objects.filter(event_type="yellow_card").count()
    total_reds = MatchEvent.objects.filter(event_type__in=["red_card", "second_yellow"]).count()

    context = {
        "total_appeals": total,
        "pending_response": pending_response,
        "awaiting_decision": awaiting_decision,
        "decided": decided,
        "my_decisions": my_decisions,
        "recent_appeals": recent_appeals,
        # New competition data stats
        "total_teams": total_teams,
        "total_players": total_players,
        "total_fixtures": total_fixtures,
        "completed_fixtures": completed_fixtures,
        "total_reports": total_reports,
        "total_squads": total_squads,
        "total_yellows": total_yellows,
        "total_reds": total_reds,
    }
    return render(request, "appeals/jury_dashboard.html", context)
