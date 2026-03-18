from django.contrib import admin
from .models import (
    Appeal, AppealEvidence, AppealResponse, ResponseEvidence,
    JuryDecision, DecisionEvidence,
)


class AppealEvidenceInline(admin.TabularInline):
    model = AppealEvidence
    extra = 0


class ResponseEvidenceInline(admin.TabularInline):
    model = ResponseEvidence
    extra = 0


class DecisionEvidenceInline(admin.TabularInline):
    model = DecisionEvidence
    extra = 0


@admin.register(Appeal)
class AppealAdmin(admin.ModelAdmin):
    list_display = ["pk", "subject", "appellant_team", "respondent_team", "status", "fee_status", "is_reappeal", "created_at"]
    list_filter = ["status", "fee_status", "is_reappeal"]
    search_fields = ["subject", "details", "appellant_team__name", "respondent_team__name"]
    inlines = [AppealEvidenceInline]
    readonly_fields = ["created_at", "submitted_at", "updated_at"]


@admin.register(AppealResponse)
class AppealResponseAdmin(admin.ModelAdmin):
    list_display = ["appeal", "respondent_user", "submitted_at"]
    inlines = [ResponseEvidenceInline]


@admin.register(JuryDecision)
class JuryDecisionAdmin(admin.ModelAdmin):
    list_display = ["appeal", "decided_by", "outcome", "is_published", "created_at"]
    list_filter = ["outcome", "is_published"]
    inlines = [DecisionEvidenceInline]
