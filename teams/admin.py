import secrets
import string
from django.contrib import admin
from django.contrib import messages
from django.utils import timezone
from .models import Team, Player, PlayerVerificationLog, LigiMashinaniRegistration


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


@admin.register(LigiMashinaniRegistration)
class LigiMashinaniRegistrationAdmin(admin.ModelAdmin):
    list_display  = [
        "team_name", "discipline", "ward", "sub_county",
        "manager_full_name", "manager_email", "manager_phone",
        "status", "account_created", "submitted_at",
    ]
    list_filter   = ["status", "sub_county", "discipline", "account_created"]
    search_fields = ["team_name", "manager_first_name", "manager_last_name", "manager_email", "ward"]
    readonly_fields = ["submitted_at", "updated_at", "account_created"]
    ordering      = ["-submitted_at"]

    fieldsets = [
        ("Team Details", {
            "fields": ["sub_county", "ward", "team_name", "discipline"],
        }),
        ("Team Manager", {
            "fields": ["manager_first_name", "manager_last_name", "manager_email", "manager_phone"],
        }),
        ("Status", {
            "fields": ["status", "rejection_reason", "account_created", "notes"],
        }),
        ("Timestamps", {
            "fields": ["submitted_at", "updated_at"],
            "classes": ["collapse"],
        }),
    ]

    actions = ["approve_and_create_accounts", "mark_ward_verified", "reject_registrations"]

    def manager_full_name(self, obj):
        return obj.manager_full_name
    manager_full_name.short_description = "Manager Name"

    def approve_and_create_accounts(self, request, queryset):
        """Approve selected registrations and auto-create Team Manager portal accounts."""
        from accounts.models import User, UserRole
        from accounts.notifications import notify_account_created

        created_count = 0
        skipped_count = 0

        for reg in queryset.filter(status__in=["pending", "ward_verified"]):
            if reg.account_created:
                skipped_count += 1
                continue

            # Check if email already taken
            if User.objects.filter(email__iexact=reg.manager_email).exists():
                self.message_user(
                    request,
                    f"⚠️ {reg.manager_email} already has an account — skipped.",
                    messages.WARNING,
                )
                continue

            # Generate a secure temporary password
            alphabet = string.ascii_letters + string.digits
            temp_password = "".join(secrets.choice(alphabet) for _ in range(10))

            user = User.objects.create_user(
                email=reg.manager_email,
                password=temp_password,
                first_name=reg.manager_first_name,
                last_name=reg.manager_last_name,
                phone=reg.manager_phone if reg.manager_phone.startswith("+") else None,
                role=UserRole.TEAM_MANAGER,
                must_change_password=True,
            )

            reg.status = "approved"
            reg.account_created = True
            reg.save(update_fields=["status", "account_created", "updated_at"])

            # Send credentials
            try:
                notify_account_created(user, temp_password, "Team Manager (Ligi Mashinani)")
            except Exception as exc:
                self.message_user(
                    request,
                    f"⚠️ Account created for {user.email} but email failed: {exc}",
                    messages.WARNING,
                )

            created_count += 1

        self.message_user(
            request,
            f"✅ {created_count} account(s) created. {skipped_count} already had accounts.",
            messages.SUCCESS,
        )

    approve_and_create_accounts.short_description = "✅ Approve & create portal accounts"

    def mark_ward_verified(self, request, queryset):
        updated = queryset.filter(status="pending").update(status="ward_verified")
        self.message_user(request, f"{updated} registration(s) marked as ward-verified.", messages.SUCCESS)
    mark_ward_verified.short_description = "🏘️ Mark as Ward Council Verified"

    def reject_registrations(self, request, queryset):
        updated = queryset.exclude(status="approved").update(status="rejected")
        self.message_user(request, f"{updated} registration(s) rejected.", messages.WARNING)
    reject_registrations.short_description = "❌ Reject selected registrations"
