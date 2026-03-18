from django.contrib import admin
from .models import Competition, Venue, Pool, PoolTeam, Fixture, CountyPayment, CountyRegistration


@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display  = ["name", "sport_type", "gender", "format_type", "is_exhibition", "season", "age_group", "status", "start_date", "end_date"]
    list_filter   = ["sport_type", "gender", "format_type", "is_exhibition", "status", "age_group", "season"]
    search_fields = ["name"]


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ["name", "county", "city", "capacity", "surface", "is_active"]
    list_filter  = ["county", "is_active"]
    search_fields = ["name", "city"]


class PoolTeamInline(admin.TabularInline):
    model  = PoolTeam
    extra  = 0
    fields = ["team", "played", "won", "drawn", "lost", "goals_for", "goals_against", "sets_won", "sets_lost", "bonus_points"]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "team":
            from teams.models import Team
            kwargs["queryset"] = Team.objects.filter(status="registered", payment_confirmed=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Pool)
class PoolAdmin(admin.ModelAdmin):
    list_display = ["name", "competition"]
    list_filter  = ["competition"]
    inlines      = [PoolTeamInline]


@admin.register(Fixture)
class FixtureAdmin(admin.ModelAdmin):
    list_display  = ["__str__", "competition", "match_date", "kickoff_time", "venue", "status", "is_knockout", "knockout_round"]
    list_filter   = ["status", "competition", "match_date", "is_knockout", "knockout_round"]
    search_fields = ["home_team__name", "away_team__name"]
    date_hierarchy = "match_date"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name in ("home_team", "away_team"):
            from teams.models import Team
            kwargs["queryset"] = Team.objects.filter(status="registered", payment_confirmed=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(CountyPayment)
class CountyPaymentAdmin(admin.ModelAdmin):
    list_display  = ["county", "season", "participation_fee", "payment_status", "payment_reference", "payment_date", "confirmed_by"]
    list_filter   = ["payment_status", "season"]
    search_fields = ["county", "payment_reference"]


@admin.register(CountyRegistration)
class CountyRegistrationAdmin(admin.ModelAdmin):
    list_display  = ["county", "competition", "county_payment", "registered_at"]
    list_filter   = ["competition"]
    search_fields = ["county"]
    readonly_fields = ["registered_at"]
    ordering       = ["competition", "county"]
