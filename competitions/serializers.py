"""
MKJ SUPA CUP Competitions — Serializers
"""
from rest_framework import serializers
from .models import Competition, Venue, Pool, PoolTeam, Fixture


class VenueSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Venue
        fields = "__all__"


class CompetitionSerializer(serializers.ModelSerializer):
    status_display     = serializers.CharField(source="get_status_display",     read_only=True)
    age_group_display  = serializers.CharField(source="get_age_group_display",  read_only=True)
    sport_type_display = serializers.CharField(source="get_sport_type_display", read_only=True)
    gender_display     = serializers.CharField(source="get_gender_display",     read_only=True)
    format_display     = serializers.CharField(source="get_format_type_display", read_only=True)
    team_count         = serializers.SerializerMethodField()
    fixture_count      = serializers.SerializerMethodField()

    class Meta:
        model  = Competition
        fields = [
            "id", "name", "sport_type", "sport_type_display",
            "gender", "gender_display",
            "format_type", "format_display",
            "is_exhibition",
            "season", "age_group", "age_group_display",
            "status", "status_display", "description", "rules",
            "start_date", "end_date", "max_teams",
            "teams_per_group", "qualify_from_group",
            "team_count", "fixture_count",
            "created_by", "created_at",
        ]
        read_only_fields = ["created_by", "created_at"]

    def get_team_count(self, obj):
        return obj.pools.aggregate(
            total=__import__("django.db.models", fromlist=["Count"]).Count(
                "pool_teams__team", distinct=True
            )
        ).get("total", 0)

    def get_fixture_count(self, obj):
        return obj.fixtures.count()

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class PoolTeamSerializer(serializers.ModelSerializer):
    team_name  = serializers.CharField(source="team.name", read_only=True)
    team_county = serializers.CharField(source="team.county", read_only=True)
    points     = serializers.IntegerField(read_only=True)
    goal_difference = serializers.IntegerField(read_only=True)

    class Meta:
        model  = PoolTeam
        fields = [
            "id", "team", "team_name", "team_county",
            "played", "won", "drawn", "lost",
            "goals_for", "goals_against", "goal_difference", "points",
        ]

    def validate_team(self, team):
        """Only teams with confirmed payment can be added to a pool."""
        if not team.payment_confirmed:
            raise serializers.ValidationError(
                f"{team.name} cannot be added to a pool — payment has not been confirmed by the treasurer."
            )
        if team.status != "registered":
            raise serializers.ValidationError(
                f"{team.name} is not registered. Only approved teams can join a pool."
            )
        return team


class PoolSerializer(serializers.ModelSerializer):
    standings = PoolTeamSerializer(source="pool_teams", many=True, read_only=True)

    class Meta:
        model  = Pool
        fields = ["id", "competition", "name", "notes", "standings"]


class FixtureSerializer(serializers.ModelSerializer):
    competition_name = serializers.CharField(source="competition.name", read_only=True)
    home_team_name   = serializers.CharField(source="home_team.name",   read_only=True)
    away_team_name   = serializers.CharField(source="away_team.name",   read_only=True)
    venue_name       = serializers.CharField(source="venue.name",       read_only=True)
    pool_name        = serializers.CharField(source="pool.name",        read_only=True)
    status_display   = serializers.CharField(source="get_status_display", read_only=True)
    referee          = serializers.SerializerMethodField()
    squad_deadline   = serializers.SerializerMethodField()
    home_squad_status = serializers.SerializerMethodField()
    away_squad_status = serializers.SerializerMethodField()

    class Meta:
        model  = Fixture
        fields = [
            "id", "competition", "competition_name",
            "pool", "pool_name",
            "home_team", "home_team_name",
            "away_team", "away_team_name",
            "venue", "venue_name",
            "match_date", "kickoff_time",
            "status", "status_display",
            "home_score", "away_score",
            "is_knockout", "knockout_round",
            "bracket_position", "leg_number",
            "home_score_et", "away_score_et",
            "home_penalties", "away_penalties",
            "winner",
            "round_number", "is_walkover",
            "referee", "squad_deadline",
            "home_squad_status", "away_squad_status",
            "created_at",
        ]
        read_only_fields = ["created_at", "created_by"]

    def get_referee(self, obj):
        try:
            appt = obj.referee_appointments.filter(role="centre").select_related("referee__user").first()
            if appt:
                return {"id": appt.referee.id, "name": appt.referee.user.get_full_name()}
        except Exception:
            pass
        return None

    def get_squad_deadline(self, obj):
        try:
            return obj.squad_deadline.isoformat()
        except Exception:
            return None

    def get_home_squad_status(self, obj):
        try:
            sq = obj.squads.filter(team=obj.home_team).first()
            return sq.status if sq else "not_submitted"
        except Exception:
            return "not_submitted"

    def get_away_squad_status(self, obj):
        try:
            sq = obj.squads.filter(team=obj.away_team).first()
            return sq.status if sq else "not_submitted"
        except Exception:
            return "not_submitted"

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        # Ensure both teams have confirmed payment before creating a fixture
        home = validated_data.get("home_team")
        away = validated_data.get("away_team")
        for t in (home, away):
            if t and not t.payment_confirmed:
                raise serializers.ValidationError(
                    {"detail": f"{t.name} has not been cleared by the treasurer. "
                     f"Fixtures can only be created for teams with confirmed payment."}
                )
        return super().create(validated_data)
