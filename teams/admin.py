import secrets
import string
import logging

from django.contrib import admin
from django.contrib import messages
from django.db import transaction
from django.utils import timezone

from .models import (
    Team, Player, PlayerVerificationLog,
    LigiMashinaniRegistration, WardLonglist,
    CountyRegistration, CountyRegStatus,
    CountyDiscipline, TeamStatus,
)

logger = logging.getLogger(__name__)


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


# ══════════════════════════════════════════════════════════════════════════════
#  LIGI MASHINANI REGISTRATION ADMIN
# ══════════════════════════════════════════════════════════════════════════════

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

    actions = ["approve_registrations", "mark_ward_verified", "reject_registrations"]

    def manager_full_name(self, obj):
        return obj.manager_full_name
    manager_full_name.short_description = "Manager Name"

    # ── Task 3.1: Atomic approval action ──────────────────────────────────
    def approve_registrations(self, request, queryset):
        """
        Atomically approve selected registrations and auto-create Team Manager portal accounts.

        For each approved registration, in a single atomic transaction:
          1. Create User (role=TEAM_MANAGER, must_change_password=True, sub_county/ward from reg)
          2. Find/create CountyRegistration at level=ward
          3. Find/create CountyDiscipline at level=ward with sub_county+ward
          4. Create Team (status=registered) linked to the discipline
          5. Create WardLonglist in draft status
          6. Set LigiMashinaniRegistration.account_created = True

        After the transaction:
          7. Send credentials email (try/except: on failure log to ActivityLog and continue)

        On any exception in the transaction: full rollback, status reverts to pending,
        error is logged to ActivityLog, and an error notice is shown to the admin.
        """
        from accounts.models import User, UserRole
        from accounts.notifications import notify_account_created
        from admin_dashboard.activity_logger import log_activity

        created_count = 0
        skipped_count = 0
        error_count = 0

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
                skipped_count += 1
                continue

            # Generate a secure temporary password
            alphabet = string.ascii_letters + string.digits
            temp_password = "".join(secrets.choice(alphabet) for _ in range(12))

            user = None
            try:
                with transaction.atomic():
                    # Step 1: Create the User account
                    phone_value = reg.manager_phone if reg.manager_phone.startswith("+") else None
                    user = User.objects.create_user(
                        email=reg.manager_email,
                        password=temp_password,
                        first_name=reg.manager_first_name,
                        last_name=reg.manager_last_name,
                        phone=phone_value,
                        role=UserRole.TEAM_MANAGER,
                        sub_county=reg.sub_county,
                        ward=reg.ward,
                        must_change_password=True,
                    )

                    # Step 2: Find or create the CountyRegistration at level=ward for Makueni
                    makueni_reg, _cr_created = CountyRegistration.objects.get_or_create(
                        county="Makueni",
                        defaults={
                            "user": user,
                            "status": CountyRegStatus.APPROVED,
                            "director_phone": reg.manager_phone,
                            "level": "ward",
                            "approved_at": timezone.now(),
                        },
                    )

                    # Step 3: Find or create the ward-level CountyDiscipline
                    discipline, _disc_created = CountyDiscipline.objects.get_or_create(
                        registration=makueni_reg,
                        sport_type=reg.discipline,
                        sub_county=reg.sub_county,
                        level="ward",
                        ward=reg.ward,
                    )

                    # Step 4: Create or update the Team record (status=registered)
                    from teams.models import County, get_or_create_county_record
                    county_obj = get_or_create_county_record("Makueni")
                    team, _team_created = Team.objects.get_or_create(
                        source_discipline=discipline,
                        defaults={
                            "name": reg.team_name,
                            "county": county_obj,
                            "sub_county": reg.sub_county,
                            "sport_type": reg.discipline,
                            "manager": user,
                            "status": TeamStatus.REGISTERED,
                            "contact_phone": reg.manager_phone,
                            "contact_email": reg.manager_email,
                            "payment_confirmed": True,
                            "payment_confirmed_at": timezone.now(),
                        },
                    )
                    if not _team_created:
                        team.manager = user
                        team.status = TeamStatus.REGISTERED
                        team.save(update_fields=["manager", "status", "updated_at"])

                    # Step 5: Create WardLonglist in draft status for the discipline
                    WardLonglist.objects.get_or_create(
                        discipline=discipline,
                        defaults={"status": "draft"},
                    )

                    # Step 6: Mark registration as approved + account created
                    reg.status = "approved"
                    reg.account_created = True
                    reg.save(update_fields=["status", "account_created", "updated_at"])

                # Step 7: Send credentials email (outside transaction — failure never rolls back)
                try:
                    notify_account_created(user, temp_password, "Team Manager (Ligi Mashinani)")
                except Exception as email_exc:
                    logger.error(
                        "Credentials email failed for %s: %s", user.email, email_exc
                    )
                    # Log email failure to ActivityLog and continue
                    try:
                        log_activity(
                            user=request.user,
                            action="ADMIN_ACTION",
                            description=(
                                f"Credentials email failed for {user.email} "
                                f"(Ligi Mashinani reg #{reg.pk} — {reg.team_name}): {email_exc}"
                            ),
                            obj=reg,
                        )
                    except Exception:
                        pass
                    self.message_user(
                        request,
                        f"⚠️ Account created for {user.email} but notification failed: {email_exc}",
                        messages.WARNING,
                    )

                # Log successful approval to ActivityLog
                try:
                    log_activity(
                        user=request.user,
                        action="ADMIN_ACTION",
                        description=(
                            f"Approved Ligi Mashinani registration for {reg.team_name} "
                            f"({reg.ward}, {reg.sub_county}) — account created for {user.email}"
                        ),
                        obj=reg,
                    )
                except Exception:
                    pass  # Activity log failure never blocks the approval

                created_count += 1

            except Exception as exc:
                # transaction.atomic() rolled back all DB changes automatically.
                # Reset the registration status to pending so the admin can retry.
                try:
                    reg.status = "pending"
                    reg.save(update_fields=["status", "updated_at"])
                except Exception:
                    pass

                logger.exception("Failed to approve Ligi registration #%d: %s", reg.pk, exc)

                # Log the failure to ActivityLog
                try:
                    log_activity(
                        user=request.user,
                        action="OTHER",
                        description=(
                            f"FAILED to approve Ligi Mashinani registration #{reg.pk} "
                            f"for {reg.team_name} ({reg.manager_email}): {exc}"
                        ),
                        obj=reg,
                    )
                except Exception:
                    pass

                self.message_user(
                    request,
                    f"❌ Failed to approve {reg.team_name} ({reg.manager_email}): {exc}",
                    messages.ERROR,
                )
                error_count += 1

        if created_count:
            self.message_user(
                request,
                f"✅ {created_count} account(s) created and approved.",
                messages.SUCCESS,
            )
        if skipped_count:
            self.message_user(
                request,
                f"ℹ️ {skipped_count} skipped (already have accounts).",
                messages.INFO,
            )

    approve_registrations.short_description = "✅ Approve & create portal accounts (atomic)"

    def mark_ward_verified(self, request, queryset):
        updated = queryset.filter(status="pending").update(status="ward_verified")
        self.message_user(request, f"{updated} registration(s) marked as ward-verified.", messages.SUCCESS)
    mark_ward_verified.short_description = "🏘️ Mark as Ward Council Verified"

    # ── Task 3.3: Rejection notification ──────────────────────────────────
    def reject_registrations(self, request, queryset):
        """Reject selected registrations and send rejection email to each manager.

        For each registration (excluding already-approved ones):
          1. Set status = rejected
          2. Send rejection email with the rejection_reason to the manager's email
             (wrapped in try/except: on failure log to logger and ActivityLog, continue)
          3. Log the rejection action to ActivityLog

        Requirements: 2.6
        """
        from accounts.notifications import _send, _base_html
        from admin_dashboard.activity_logger import log_activity

        rejected_count = 0

        for reg in queryset.exclude(status="approved"):
            reg.status = "rejected"
            reg.save(update_fields=["status", "updated_at"])

            # Build rejection email body using the manager's registered email (Req 2.6)
            reason_text = (
                reg.rejection_reason.strip()
                if reg.rejection_reason
                else "Your registration did not meet the required criteria."
            )
            body = f"""
<p>Dear <strong>{reg.manager_first_name} {reg.manager_last_name}</strong>,</p>
<p>Thank you for registering your team <strong>{reg.team_name}</strong> for Ligi Mashinani
   ({reg.ward}, {reg.sub_county}).</p>
<p>Unfortunately, your registration has been <strong>declined</strong> for the following reason:</p>
<div class="alert">{reason_text}</div>
<p>If you believe this decision was made in error or you would like to appeal,
   please contact the MKJ SUPA CUP administration team.</p>
<a href="mailto:info@mkjsupacup.com" class="btn">Contact Administration</a>"""

            try:
                _send(
                    "Ligi Mashinani Registration — Update",
                    _base_html("Registration Status Update", body),
                    [reg.manager_email],
                )
            except Exception as email_exc:
                logger.error(
                    "Rejection email failed for %s: %s", reg.manager_email, email_exc
                )
                # Log email failure to ActivityLog and continue — never abort the rejection
                try:
                    log_activity(
                        user=request.user,
                        action="ADMIN_ACTION",
                        description=(
                            f"Rejection email failed for {reg.manager_email} "
                            f"(Ligi Mashinani reg #{reg.pk} — {reg.team_name}): {email_exc}"
                        ),
                        obj=reg,
                    )
                except Exception:
                    pass
                self.message_user(
                    request,
                    f"⚠️ {reg.team_name} rejected but notification email failed: {email_exc}",
                    messages.WARNING,
                )

            # Log the rejection to ActivityLog
            try:
                log_activity(
                    user=request.user,
                    action="ADMIN_ACTION",
                    description=(
                        f"Rejected Ligi Mashinani registration for {reg.team_name} "
                        f"({reg.ward}, {reg.sub_county}) — notified {reg.manager_email}. "
                        f"Reason: {reason_text}"
                    ),
                    obj=reg,
                )
            except Exception:
                pass  # Activity log failure never blocks the rejection

            rejected_count += 1

        if rejected_count:
            self.message_user(
                request,
                f"❌ {rejected_count} registration(s) rejected and notified.",
                messages.WARNING,
            )

    reject_registrations.short_description = "❌ Reject selected registrations"


# ══════════════════════════════════════════════════════════════════════════════
#  WARD LONGLIST ADMIN
# ══════════════════════════════════════════════════════════════════════════════

@admin.register(WardLonglist)
class WardLonglistAdmin(admin.ModelAdmin):
    list_display  = ["discipline", "status", "submitted_at", "reviewed_by", "reviewed_at"]
    list_filter   = ["status", "discipline__sub_county"]
    search_fields = ["discipline__ward", "discipline__sub_county"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]
