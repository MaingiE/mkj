"""
MKJ SUPA CUP Teams - Serializers
"""
from rest_framework import serializers
from .models import Team, Player


class PlayerSerializer(serializers.ModelSerializer):
    full_name       = serializers.SerializerMethodField()
    age             = serializers.IntegerField(read_only=True)
    position_display = serializers.CharField(source="get_position_display", read_only=True)
    status_display  = serializers.CharField(source="get_status_display",   read_only=True)

    class Meta:
        model  = Player
        fields = [
            "id", "team", "first_name", "last_name", "full_name",
            "date_of_birth", "age", "position", "position_display",
            "shirt_number", "national_id_number", "photo",
            "status", "status_display", "registered_at",
        ]
        read_only_fields = ["registered_at"]

    def get_full_name(self, obj):
        return obj.get_full_name()


class TeamSerializer(serializers.ModelSerializer):
    player_count   = serializers.SerializerMethodField()
    manager_name   = serializers.CharField(source="manager.get_full_name", read_only=True)
    status_display = serializers.CharField(source="get_status_display",    read_only=True)

    class Meta:
        model  = Team
        fields = [
            "id", "name", "county", "competition",
            "manager", "manager_name",
            "status", "status_display",
            "badge", "home_colour", "away_colour",
            "contact_phone", "contact_email",
            "player_count", "registered_at",
        ]
        read_only_fields = ["registered_at"]

    def get_player_count(self, obj):
        return obj.players.count()


class TeamDetailSerializer(TeamSerializer):
    players = PlayerSerializer(many=True, read_only=True)

    class Meta(TeamSerializer.Meta):
        fields = TeamSerializer.Meta.fields + ["players"]
