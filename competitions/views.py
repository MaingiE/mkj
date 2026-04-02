"""
MKJ SUPA CUP Competitions - Views
"""
from rest_framework import generics, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from drf_spectacular.utils import extend_schema

from .models import Competition, Venue, Pool, PoolTeam, Fixture, KnockoutRound, FixtureStatus
from .serializers import (
    CompetitionSerializer, VenueSerializer,
    PoolSerializer, PoolTeamSerializer, FixtureSerializer,
)
from accounts.permissions import IsCompetitionManager, ReadOnly


# ── COMPETITION ───────────────────────────────────────────────────────────────

class CompetitionViewSet(ModelViewSet):
    """
    Competition Manager: full CRUD
    Others: read-only
    """
    queryset         = Competition.objects.all()
    serializer_class = CompetitionSerializer
    filterset_fields = ["status", "age_group", "season"]
    search_fields    = ["name"]
    ordering_fields  = ["start_date", "name"]

    def get_permissions(self):
        if self.action in ("list", "retrieve", "auto_create_final"):
            return [permissions.AllowAny()]
        return [IsCompetitionManager()]

    @extend_schema(tags=["competitions"])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="auto-create-final")
    def auto_create_final(self, request, pk=None):
        """Auto-create Final + 3rd-place fixtures when both semis are completed."""
        comp = self.get_object()
        semis = Fixture.objects.filter(
            competition=comp,
            is_knockout=True,
            knockout_round=KnockoutRound.SEMIFINAL,
        ).select_related("winner")

        if semis.count() < 2:
            return Response({"detail": "Less than 2 semi-finals found."}, status=status.HTTP_400_BAD_REQUEST)

        if not all(s.status == FixtureStatus.COMPLETED and s.winner for s in semis):
            return Response({"detail": "Not all semi-finals completed yet."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if final already exists
        if Fixture.objects.filter(competition=comp, is_knockout=True, knockout_round=KnockoutRound.FINAL).exists():
            return Response({"detail": "Final already exists."}, status=status.HTTP_200_OK)

        semis = list(semis.order_by("bracket_position"))
        winners = [s.winner for s in semis]
        losers = []
        for s in semis:
            losers.append(s.away_team if s.winner == s.home_team else s.home_team)

        ref_semi = semis[0]
        final = Fixture.objects.create(
            competition=comp,
            home_team=winners[0],
            away_team=winners[1],
            match_date=ref_semi.match_date,
            kickoff_time="14:00",
            is_knockout=True,
            knockout_round=KnockoutRound.FINAL,
            bracket_position=1,
        )
        third = Fixture.objects.create(
            competition=comp,
            home_team=losers[0],
            away_team=losers[1],
            match_date=ref_semi.match_date,
            kickoff_time="12:00",
            is_knockout=True,
            knockout_round=KnockoutRound.THIRD_PLACE,
            bracket_position=1,
        )
        return Response({
            "detail": "Final and 3rd-place match created.",
            "final_id": final.pk,
            "third_place_id": third.pk,
        }, status=status.HTTP_201_CREATED)


# ── VENUE ─────────────────────────────────────────────────────────────────────

class VenueViewSet(ModelViewSet):
    queryset         = Venue.objects.filter(is_active=True)
    serializer_class = VenueSerializer
    filterset_fields = ["county", "is_active"]
    search_fields    = ["name", "city", "county"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.IsAuthenticated()]
        return [IsCompetitionManager()]

    @extend_schema(tags=["venues"])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


# ── POOL ──────────────────────────────────────────────────────────────────────

class PoolViewSet(ModelViewSet):
    queryset         = Pool.objects.all().select_related("competition")
    serializer_class = PoolSerializer
    filterset_fields = ["competition"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.IsAuthenticated()]
        return [IsCompetitionManager()]

    @extend_schema(tags=["pools"])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class PoolTeamManageView(generics.CreateAPIView):
    """Add a team to a pool - Competition Manager only."""
    serializer_class   = PoolTeamSerializer
    permission_classes = [IsCompetitionManager]

    @extend_schema(tags=["pools"], summary="Add team to pool")
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


# ── FIXTURE ───────────────────────────────────────────────────────────────────

class FixtureViewSet(ModelViewSet):
    """
    Competition Manager: create, update, delete.
    Authenticated users: read.
    """
    queryset = Fixture.objects.all().select_related(
        "competition", "home_team", "away_team", "venue", "pool"
    )
    serializer_class = FixtureSerializer
    filterset_fields = ["competition", "status", "match_date", "home_team", "away_team", "venue"]
    search_fields    = ["home_team__name", "away_team__name"]
    ordering_fields  = ["match_date", "kickoff_time"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.IsAuthenticated()]
        return [IsCompetitionManager()]

    @extend_schema(tags=["fixtures"])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(tags=["fixtures"], summary="Update fixture score / status")
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @action(detail=True, methods=["get"], url_path="squads")
    @extend_schema(tags=["squads"], summary="Get both teams' submitted squads for a fixture")
    def squads(self, request, pk=None):
        from matches.models import SquadSubmission
        from matches.serializers import SquadSubmissionSerializer
        fixture = self.get_object()
        squads  = SquadSubmission.objects.filter(fixture=fixture).select_related("team")
        return Response(SquadSubmissionSerializer(squads, many=True).data)
