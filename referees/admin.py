from django.contrib import admin
from .models import RefereeProfile, RefereeCertification, RefereeAppointment, RefereeReview, RefereeAvailability


class CertInline(admin.TabularInline):
    model  = RefereeCertification
    extra  = 0


@admin.register(RefereeProfile)
class RefereeProfileAdmin(admin.ModelAdmin):
    list_display  = ["__str__", "level", "county", "is_approved", "total_matches", "avg_rating"]
    list_filter   = ["is_approved", "level", "county"]
    search_fields = ["user__first_name", "user__last_name", "license_number"]
    inlines       = [CertInline]
    readonly_fields = ["total_matches", "avg_rating", "approved_at"]

    actions = ["approve_referees"]

    def approve_referees(self, request, queryset):
        from django.utils import timezone
        queryset.update(is_approved=True, approved_by=request.user, approved_at=timezone.now())
    approve_referees.short_description = "✅ Approve selected referees"


@admin.register(RefereeAppointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ["referee", "fixture", "role", "status", "appointed_at"]
    list_filter  = ["status", "role"]


@admin.register(RefereeReview)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["referee", "fixture", "overall_score", "reviewer", "reviewed_at"]
    list_filter  = ["overall_score"]
