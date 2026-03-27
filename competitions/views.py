"""
MKJ SUPA CUP Competitions - Views
"""
from rest_framework import generics, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from drf_spectacular.utils import extend_schema

from .models import Competition, Venue, Pool, PoolTeam, Fixture
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
        if self.action in ("list", "retrieve"):
            return [permissions.IsAuthenticated()]
        return [IsCompetitionManager()]

    @extend_schema(tags=["competitions"])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


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
