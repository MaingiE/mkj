from django.contrib import admin
from .models import Team, Player, PlayerVerificationLog


class PlayerInline(admin.TabularInline):
    model  = Player
    extra  = 0
    fields = ["shirt_number", "first_name", "last_name", "position", "status"]


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display  = ["name", "county", "manager", "status", "registered_at"]
    list_filter   = ["status", "county", "competition"]
    search_fields = ["name", "county"]
    inlines       = [PlayerInline]

    actions = ["approve_teams"]

    def approve_teams(self, request, queryset):
        queryset.update(status="registered")
    approve_teams.short_description = "✅ Approve selected teams"


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display  = ["__str__", "position", "age", "status", "huduma_status", "fifa_connect_status"]
    list_filter   = ["position", "status", "huduma_status", "fifa_connect_status", "team__county"]
    search_fields = ["first_name", "last_name", "team__name", "national_id_number", "fifa_connect_id"]


@admin.register(PlayerVerificationLog)
class PlayerVerificationLogAdmin(admin.ModelAdmin):
    list_display  = ["player", "step", "action", "result", "performed_by", "performed_at"]
    list_filter   = ["step", "action", "result"]
    search_fields = ["player__first_name", "player__last_name", "notes"]
    readonly_fields = ["player", "step", "action", "result", "details", "notes", "performed_by", "performed_at"]
