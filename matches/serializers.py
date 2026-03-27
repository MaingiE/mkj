"""
MKJ SUPA CUP Matches - Serializers
"""
from rest_framework import serializers
from django.utils import timezone
from .models import SquadSubmission, SquadPlayer, MatchReport, MatchEvent


class SquadPlayerSerializer(serializers.ModelSerializer):
    player_name    = serializers.CharField(source="player.get_full_name",     read_only=True)
    position       = serializers.CharField(source="player.position",          read_only=True)
    position_display = serializers.CharField(source="player.get_position_display", read_only=True)

    class Meta:
        model  = SquadPlayer
        fields = ["id", "player", "player_name", "position", "position_display", "shirt_number", "is_starter"]


class SquadSubmissionSerializer(serializers.ModelSerializer):
    squad_players  = SquadPlayerSerializer(many=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    team_name      = serializers.CharField(source="team.name",          read_only=True)
    deadline       = serializers.SerializerMethodField()

    class Meta:
        model  = SquadSubmission
        fields = [
            "id", "fixture", "team", "team_name",
            "status", "status_display",
            "squad_players", "deadline",
            "submitted_at", "reviewed_at", "rejection_reason",
        ]
        read_only_fields = ["submitted_at", "reviewed_at", "reviewed_by"]

    def get_deadline(self, obj):
        try:
            return obj.fixture.squad_deadline.isoformat()
        except Exception:
            return None

    def validate(self, data):
        fixture = data.get("fixture") or self.instance.fixture
        # Check deadline
        try:
            deadline = fixture.squad_deadline
            if timezone.now() > deadline:
                raise serializers.ValidationError(
                    f"Squad submission deadline has passed. Deadline was {deadline.strftime('%Y-%m-%d %H:%M')}."
                )
        except AttributeError:
            pass

        # Validate player counts
        players = data.get("squad_players", [])
        if players:
            from django.conf import settings as conf
            min_p = getattr(conf, "SQUAD_MIN_PLAYERS",  11)
            max_p = getattr(conf, "SQUAD_MAX_PLAYERS",  16)
            starters = [p for p in players if p.get("is_starter")]
            subs     = [p for p in players if not p.get("is_starter")]

            if len(players) < min_p:
                raise serializers.ValidationError(f"Squad must have at least {min_p} players.")
            if len(players) > max_p:
                raise serializers.ValidationError(f"Squad cannot exceed {max_p} players.")
            if len(starters) != 11:
                raise serializers.ValidationError("Exactly 11 starters are required.")
            if len(subs) > 5:
                raise serializers.ValidationError("Maximum 5 substitutes allowed.")
        return data

    def create(self, validated_data):
        players_data = validated_data.pop("squad_players", [])
        submission   = SquadSubmission.objects.create(**validated_data)
        for pd in players_data:
            SquadPlayer.objects.create(submission=submission, **pd)
        return submission


class SquadApprovalSerializer(serializers.Serializer):
    action           = serializers.ChoiceField(choices=["approve", "reject"])
    rejection_reason = serializers.CharField(required=False, allow_blank=True)


class MatchEventSerializer(serializers.ModelSerializer):
    player_name = serializers.CharField(source="player.get_full_name", read_only=True)
    team_name   = serializers.CharField(source="team.name",            read_only=True)

    class Meta:
        model  = MatchEvent
        fields = ["id", "team", "team_name", "player", "player_name", "event_type", "minute", "notes"]


class MatchReportSerializer(serializers.ModelSerializer):
    events         = MatchEventSerializer(many=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    fixture_label  = serializers.SerializerMethodField()

    class Meta:
        model  = MatchReport
        fields = [
            "id", "fixture", "fixture_label", "referee", "appointment_snapshot",
            "status", "status_display",
            "home_score", "away_score",
            "home_yellow_cards", "away_yellow_cards",
            "home_red_cards", "away_red_cards",
            "match_duration", "added_time_ht", "added_time_ft",
            "pitch_condition", "weather", "attendance",
            "referee_notes", "is_abandoned", "abandonment_reason",
            "events", "submitted_at", "reviewed_at", "reviewer_notes",
        ]
        read_only_fields = ["referee", "appointment_snapshot", "submitted_at", "reviewed_at", "reviewed_by"]

    def get_fixture_label(self, obj):
        f = obj.fixture
        return f"{f.home_team} vs {f.away_team} - {f.match_date}"

    def create(self, validated_data):
        events_data = validated_data.pop("events", [])
        report      = MatchReport.objects.create(**validated_data)
        for ed in events_data:
            MatchEvent.objects.create(report=report, **ed)
        return report


class MatchReportApprovalSerializer(serializers.Serializer):
    action         = serializers.ChoiceField(choices=["approve", "return"])
    reviewer_notes = serializers.CharField(required=False, allow_blank=True)
