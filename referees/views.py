"""
MKJ SUPA CUP Referees - Views
"""
from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from django.utils import timezone
from drf_spectacular.utils import extend_schema

from .models import RefereeProfile, RefereeAppointment, RefereeAvailability, RefereeReview
from .serializers import (
    RefereeProfileSerializer, RefereeApprovalSerializer,
    RefereeAppointmentSerializer, RefereeAvailabilitySerializer,
    RefereeReviewSerializer,
)
from accounts.permissions import IsRefereeManager, IsReferee, IsRefereeManagerOrAdmin


class RefereeListView(generics.ListAPIView):
    """GET /api/v1/referees/ - list all referee profiles"""
    serializer_class   = RefereeProfileSerializer
    filterset_fields   = ["is_approved", "level", "county"]
    search_fields      = ["user__first_name", "user__last_name", "license_number"]

    def get_queryset(self):
        return RefereeProfile.objects.select_related("user").all()

    @extend_schema(tags=["referees"], summary="List all referees")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class RefereeDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/v1/referees/<id>/"""
    serializer_class = RefereeProfileSerializer
    queryset         = RefereeProfile.objects.select_related("user").all()

    def get_permissions(self):
        if self.request.method == "GET":
            return [permissions.IsAuthenticated()]
        return [IsReferee()]

    @extend_schema(tags=["referees"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class RefereeRegisterView(generics.CreateAPIView):
    """POST /api/v1/referees/register/ - Referee creates their profile (after account registration)"""
    serializer_class   = RefereeProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["referees"], summary="Referee submits registration profile")
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class RefereeApproveView(APIView):
    """POST /api/v1/referees/<id>/approve/ - Referee Manager approves or rejects"""
    permission_classes = [IsRefereeManagerOrAdmin]

    @extend_schema(tags=["referees"], summary="Approve or reject referee registration")
    def post(self, request, pk):
        try:
            referee = RefereeProfile.objects.get(pk=pk)
        except RefereeProfile.DoesNotExist:
            return Response({"detail": "Referee not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = RefereeApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        approved = serializer.validated_data["is_approved"]
        referee.is_approved  = approved
        referee.approved_by  = request.user
        referee.approved_at  = timezone.now() if approved else None
        referee.save()

        # TODO: send email notification to referee
        action = "approved" if approved else "rejected"
        return Response({"detail": f"Referee registration {action}.", "is_approved": approved})


class MyAppointmentsView(generics.ListAPIView):
    """GET /api/v1/referees/my-appointments/ - referee views their own appointments"""
    serializer_class   = RefereeAppointmentSerializer
    permission_classes = [IsReferee]
    filterset_fields   = ["status", "fixture__match_date"]

    def get_queryset(self):
        return RefereeAppointment.objects.filter(
            referee=self.request.user.referee_profile
        ).select_related("fixture", "fixture__home_team", "fixture__away_team")

    @extend_schema(tags=["referees"], summary="My assigned fixtures (referee)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AppointmentConfirmView(APIView):
    """POST /api/v1/referees/appointments/<id>/confirm/"""
    permission_classes = [IsReferee]

    @extend_schema(tags=["referees"], summary="Referee confirms or declines appointment")
    def post(self, request, pk):
        try:
            appt = RefereeAppointment.objects.get(pk=pk, referee=request.user.referee_profile)
        except RefereeAppointment.DoesNotExist:
            return Response({"detail": "Appointment not found."}, status=404)

        action = request.data.get("action")  # "confirm" or "decline"
        if action == "confirm":
            appt.status       = "confirmed"
            appt.confirmed_at = timezone.now()
        elif action == "decline":
            appt.status = "declined"
        else:
            return Response({"detail": "action must be 'confirm' or 'decline'."}, status=400)
        appt.save()
        return Response({"detail": f"Appointment {appt.status}.", "status": appt.status})


class AppointmentViewSet(ModelViewSet):
    """Referee Manager manages all appointments."""
    serializer_class   = RefereeAppointmentSerializer
    permission_classes = [IsRefereeManagerOrAdmin]
    filterset_fields   = ["fixture", "referee", "role", "status"]

    def get_queryset(self):
        return RefereeAppointment.objects.select_related(
            "fixture", "referee__user"
        ).all()

    @extend_schema(tags=["referees"])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class AvailabilityViewSet(ModelViewSet):
    """Referee manages their own availability."""
    serializer_class   = RefereeAvailabilitySerializer
    permission_classes = [IsReferee]

    def get_queryset(self):
        return RefereeAvailability.objects.filter(
            referee=self.request.user.referee_profile
        )

    @extend_schema(tags=["referees"], summary="Set my availability")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class ReviewViewSet(ModelViewSet):
    """Referee Manager creates/views reviews."""
    serializer_class = RefereeReviewSerializer
    filterset_fields = ["referee", "fixture"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.IsAuthenticated()]
        return [IsRefereeManagerOrAdmin()]

    def get_queryset(self):
        return RefereeReview.objects.select_related("referee__user", "reviewer").all()

    @extend_schema(tags=["referees"])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
