"""
MKJ SUPA CUP Referees — Serializers
"""
from rest_framework import serializers
from django.utils import timezone
from .models import (
    RefereeProfile, RefereeCertification,
    RefereeAppointment, RefereeAvailability, RefereeReview,
)


class RefereeCertificationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = RefereeCertification
        fields = "__all__"
        read_only_fields = ["referee"]


class RefereeProfileSerializer(serializers.ModelSerializer):
    full_name      = serializers.CharField(source="user.get_full_name", read_only=True)
    email          = serializers.CharField(source="user.email",         read_only=True)
    phone          = serializers.CharField(source="user.phone",         read_only=True)
    level_display  = serializers.CharField(source="get_level_display",  read_only=True)
    certifications = RefereeCertificationSerializer(many=True, read_only=True)

    class Meta:
        model  = RefereeProfile
        fields = [
            "id", "user", "full_name", "email", "phone",
            "license_number", "level", "level_display",
            "county", "is_approved", "approved_at",
            "id_number", "bio", "years_experience",
            "total_matches", "avg_rating",
            "certifications", "created_at",
        ]
        read_only_fields = ["is_approved", "approved_by", "approved_at", "total_matches", "avg_rating"]


class RefereeApprovalSerializer(serializers.Serializer):
    is_approved = serializers.BooleanField()
    notes       = serializers.CharField(required=False, allow_blank=True)


class RefereeAppointmentSerializer(serializers.ModelSerializer):
    referee_name  = serializers.CharField(source="referee.user.get_full_name", read_only=True)
    fixture_label = serializers.SerializerMethodField()
    role_display  = serializers.CharField(source="get_role_display",   read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model  = RefereeAppointment
        fields = [
            "id", "fixture", "fixture_label",
            "referee", "referee_name",
            "role", "role_display",
            "status", "status_display",
            "appointed_at", "confirmed_at", "notes",
        ]
        read_only_fields = ["appointed_by", "appointed_at", "confirmed_at"]

    def get_fixture_label(self, obj):
        f = obj.fixture
        return f"{f.home_team} vs {f.away_team} — {f.match_date}"

    def create(self, validated_data):
        validated_data["appointed_by"] = self.context["request"].user
        return super().create(validated_data)


class RefereeAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model  = RefereeAvailability
        fields = ["id", "date", "status", "notes"]

    def create(self, validated_data):
        validated_data["referee"] = self.context["request"].user.referee_profile
        return super().create(validated_data)


class RefereeReviewSerializer(serializers.ModelSerializer):
    referee_name = serializers.CharField(source="referee.user.get_full_name", read_only=True)
    reviewer_name = serializers.CharField(source="reviewer.get_full_name",   read_only=True)

    class Meta:
        model  = RefereeReview
        fields = [
            "id", "referee", "referee_name",
            "fixture", "reviewer", "reviewer_name",
            "overall_score", "positioning", "decision_making",
            "fitness", "communication", "notes", "reviewed_at",
        ]
        read_only_fields = ["reviewer", "reviewed_at"]

    def create(self, validated_data):
        validated_data["reviewer"] = self.context["request"].user
        review = super().create(validated_data)
        # Recalculate avg_rating on the referee profile
        ref = review.referee
        reviews = ref.reviews.all()
        if reviews.exists():
            ref.avg_rating = reviews.aggregate(
                avg=__import__("django.db.models", fromlist=["Avg"]).Avg("overall_score")
            )["avg"] or 0
            ref.save(update_fields=["avg_rating"])
        return review
