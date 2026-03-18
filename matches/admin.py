from django.contrib import admin
from .models import SquadSubmission, SquadPlayer, MatchReport, MatchEvent, PlayerStatistics


class SquadPlayerInline(admin.TabularInline):
    model  = SquadPlayer
    extra  = 0
    fields = ["shirt_number", "player", "is_starter"]


@admin.register(SquadSubmission)
class SquadAdmin(admin.ModelAdmin):
    list_display  = ["fixture", "team", "status", "submitted_at"]
    list_filter   = ["status"]
    inlines       = [SquadPlayerInline]

    actions = ["approve_squads"]

    def approve_squads(self, request, queryset):
        from django.utils import timezone
        queryset.filter(status="submitted").update(
            status="approved", reviewed_by=request.user, reviewed_at=timezone.now()
        )
    approve_squads.short_description = "✅ Approve selected squads"


class EventInline(admin.TabularInline):
    model  = MatchEvent
    extra  = 0
    fields = ["minute", "event_type", "team", "player", "notes"]


@admin.register(MatchReport)
class MatchReportAdmin(admin.ModelAdmin):
    list_display  = ["fixture", "referee", "home_score", "away_score", "status", "submitted_at"]
    list_filter   = ["status", "pitch_condition"]
    search_fields = ["fixture__home_team__name", "fixture__away_team__name"]
    inlines       = [EventInline]
    readonly_fields = ["submitted_at", "reviewed_at"]


@admin.register(PlayerStatistics)
class PlayerStatisticsAdmin(admin.ModelAdmin):
    list_display  = ["player", "competition", "team", "matches_played", "goals", "assists", "yellow_cards", "red_cards", "clean_sheets"]
    list_filter   = ["competition", "team"]
    search_fields = ["player__first_name", "player__last_name", "team__name"]
    readonly_fields = ["goal_contributions", "updated_at"]
