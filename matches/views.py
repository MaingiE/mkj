"""
MKJ SUPA CUP Matches - Views
"""
from rest_framework import generics, status, permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from django.utils import timezone
from drf_spectacular.utils import extend_schema

from .models import SquadSubmission, MatchReport
from .serializers import (
    SquadSubmissionSerializer, SquadApprovalSerializer,
    MatchReportSerializer, MatchReportApprovalSerializer,
)
from accounts.permissions import IsReferee, IsTeamManager, IsRefereeManagerOrAdmin
from referees.models import RefereeAppointment, AppointmentStatus, get_head_official_role


# ══════════════════════════════════════════════════════════════════════════════
#  SQUAD FLOWS
# ══════════════════════════════════════════════════════════════════════════════

class SquadSubmitView(generics.CreateAPIView):
    """
    POST /api/v1/matches/squads/
    Team Manager submits squad for a fixture (≥4 hrs before KO).
    """
    serializer_class   = SquadSubmissionSerializer
    permission_classes = [IsTeamManager]

    @extend_schema(tags=["squads"], summary="Team Manager submits squad sheet")
    def perform_create(self, serializer):
        serializer.save(
            team=self.request.user.managed_teams.first(),
            status="submitted",
            submitted_at=timezone.now(),
        )


class SquadListView(generics.ListAPIView):
    """
    GET /api/v1/matches/squads/?fixture=<id>
    Referee / CM views squads for a fixture.
    """
    serializer_class   = SquadSubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields   = ["fixture", "team", "status"]

    def get_queryset(self):
        return SquadSubmission.objects.prefetch_related(
            "squad_players__player"
        ).select_related("team", "fixture").all()

    @extend_schema(tags=["squads"], summary="List squad submissions")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class SquadApproveView(APIView):
    """
    POST /api/v1/matches/squads/<id>/approve/
    Referee approves or rejects a submitted squad.
    """
    permission_classes = [IsReferee]

    @extend_schema(tags=["squads"], summary="Referee approves/rejects squad sheet")
    def post(self, request, pk):
        try:
            squad = SquadSubmission.objects.get(pk=pk, status="submitted")
        except SquadSubmission.DoesNotExist:
            return Response({"detail": "Squad not found or not in submitted state."}, status=404)

        serializer = SquadApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action  = serializer.validated_data["action"]
        reason  = serializer.validated_data.get("rejection_reason", "")

        if action == "approve":
            squad.status      = "approved"
            squad.reviewed_by = request.user
            squad.reviewed_at = timezone.now()
        else:
            squad.status           = "rejected"
            squad.reviewed_by      = request.user
            squad.reviewed_at      = timezone.now()
            squad.rejection_reason = reason

        squad.save()
        # TODO: notify team manager via email
        return Response({
            "detail": f"Squad {action}d successfully.",
            "status": squad.status,
            "rejection_reason": squad.rejection_reason,
        })


# ══════════════════════════════════════════════════════════════════════════════
#  MATCH REPORT FLOWS
# ══════════════════════════════════════════════════════════════════════════════

class MatchReportViewSet(ModelViewSet):
    """
    Referee: create / update own reports.
    Referee Manager: list, retrieve, approve.
    """
    serializer_class = MatchReportSerializer
    filterset_fields = ["status", "fixture"]

    def get_queryset(self):
        user = self.request.user
        qs   = MatchReport.objects.select_related("fixture", "referee__user").all()
        # Referees only see their own reports
        if user.is_referee:
            try:
                return qs.filter(referee=user.referee_profile)
            except Exception:
                return qs.none()
        return qs

    def get_permissions(self):
        if self.action == "create":
            return [IsReferee()]
        if self.action in ("update", "partial_update"):
            return [IsReferee()]
        return [permissions.IsAuthenticated()]

    def _require_confirmed_head_official(self, fixture):
        required_role = get_head_official_role(fixture.competition.sport_type)
        has_appointment = RefereeAppointment.objects.filter(
            fixture=fixture,
            referee=self.request.user.referee_profile,
            role=required_role,
            status=AppointmentStatus.CONFIRMED,
        ).exists()
        if not has_appointment:
            raise PermissionDenied("Only the confirmed head official appointed to this fixture may submit or edit the match report.")

    @extend_schema(tags=["matches"], summary="Submit match report (referee)")
    def perform_create(self, serializer):
        fixture = serializer.validated_data["fixture"]
        self._require_confirmed_head_official(fixture)
        serializer.save(
            referee=self.request.user.referee_profile,
            submitted_at=timezone.now(),
            status="submitted",
        )

    def perform_update(self, serializer):
        fixture = serializer.validated_data.get("fixture", serializer.instance.fixture)
        self._require_confirmed_head_official(fixture)
        serializer.save(referee=self.request.user.referee_profile)

    @extend_schema(tags=["matches"])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class MatchReportApproveView(APIView):
    """
    POST /api/v1/matches/reports/<id>/approve/
    Referee Manager approves or returns a match report.
    """
    permission_classes = [IsRefereeManagerOrAdmin]

    @extend_schema(tags=["matches"], summary="Referee Manager approves/returns match report")
    def post(self, request, pk):
        try:
            report = MatchReport.objects.get(pk=pk, status="submitted")
        except MatchReport.DoesNotExist:
            return Response({"detail": "Report not found or not in submitted state."}, status=404)

        serializer = MatchReportApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action = serializer.validated_data["action"]
        notes  = serializer.validated_data.get("reviewer_notes", "")

        if action == "approve":
            report.status       = "approved"
            report.reviewed_at  = timezone.now()
            report.reviewed_by  = request.user
            report.reviewer_notes = notes
            # Update the fixture score from the report
            fixture = report.fixture
            fixture.home_score = report.home_score
            fixture.away_score = report.away_score
            fixture.status     = "completed"
            fixture.save(update_fields=["home_score", "away_score", "status"])
            # Auto-update standings and player statistics
            from matches.stats_engine import process_approved_report
            process_approved_report(report)
        else:
            report.status       = "returned"
            report.reviewer_notes = notes

        report.save()
        return Response({"detail": f"Match report {action}d.", "status": report.status})


def _update_standings(fixture):
    """
    Legacy helper - delegates to stats_engine.
    Kept for backward compatibility with web_views.py calls.
    """
    from matches.stats_engine import update_pool_standings
    update_pool_standings(fixture)
