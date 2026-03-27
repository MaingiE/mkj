"""
MKJ SUPA CUP Teams - Views
"""
from rest_framework import generics, permissions
from rest_framework.viewsets import ModelViewSet
from drf_spectacular.utils import extend_schema

from .models import Team, Player
from .serializers import TeamSerializer, TeamDetailSerializer, PlayerSerializer
from accounts.permissions import IsCompetitionManager, IsTeamManager


class TeamViewSet(ModelViewSet):
    queryset         = Team.objects.select_related("manager").all()
    filterset_fields = ["county", "status", "competition"]
    search_fields    = ["name", "county"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return TeamDetailSerializer
        return TeamSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.IsAuthenticated()]
        if self.action == "create":
            return [IsTeamManager()]
        return [IsCompetitionManager()]

    def perform_create(self, serializer):
        serializer.save(manager=self.request.user)

    @extend_schema(tags=["teams"])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class PlayerViewSet(ModelViewSet):
    serializer_class = PlayerSerializer
    filterset_fields = ["team", "position", "status"]
    search_fields    = ["first_name", "last_name", "shirt_number"]

    def get_queryset(self):
        return Player.objects.select_related("team").all()

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.IsAuthenticated()]
        return [IsTeamManager()]

    @extend_schema(tags=["players"])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        # Ensure team manager can only add to their own team
        user = self.request.user
        if hasattr(user, "managed_teams") and user.managed_teams.exists():
            serializer.save(team=user.managed_teams.first())
        else:
            serializer.save()
