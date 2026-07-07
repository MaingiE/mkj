from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.core.exceptions import ValidationError
from .models import User, UserRole


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display  = [
        "email", "get_full_name", "role", "county", "sub_county", "ward",
        "pending_longlist_count", "is_active", "date_joined",
    ]
    list_filter   = ["role", "county", "sub_county", "ward", "is_active", "is_staff"]
    search_fields = ["email", "first_name", "last_name"]
    ordering      = ["last_name", "first_name"]

    fieldsets = (
        (None,        {"fields": ("email", "password")}),
        ("Personal",  {"fields": ("first_name", "last_name", "phone", "profile_photo")}),
        ("MKJ SUPA CUP", {"fields": ("role", "county", "sub_county", "ward", "assigned_discipline")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates",     {"fields": ("date_joined", "last_login")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "email", "first_name", "last_name",
                "role", "county", "sub_county", "ward", "assigned_discipline",
                "password1", "password2",
            ),
        }),
    )
    readonly_fields = ["date_joined", "last_login"]

    @admin.display(description="Pending Reviews")
    def pending_longlist_count(self, obj):
        """
        For WSCC users: count of WardLonglist records in 'submitted' status
        scoped to their assigned ward.  Returns '-' for all other roles.
        """
        if obj.role != UserRole.WARD_SPORTS_COUNCIL_CHAIR or not obj.ward:
            return "-"
        # Avoid a hard import at module level to keep the apps loosely coupled;
        # the teams app is always installed so the lazy import is safe here.
        from teams.models import WardLonglist, WardLonglistStatus
        return WardLonglist.objects.filter(
            discipline__ward=obj.ward,
            status=WardLonglistStatus.SUBMITTED,
        ).count()

    def save_model(self, request, obj, form, change):
        # Require assigned_discipline for coordinators and scouts
        if obj.role in ["coordinator", "scout"] and not obj.assigned_discipline:
            raise ValidationError("Discipline is required for coordinators and scouts.")

        # When a WSCC is being deactivated, surface a warning about pending reviews
        # that must be manually reassigned (Requirement 10.3).
        if (
            change  # only on updates, not new creates
            and obj.role == UserRole.WARD_SPORTS_COUNCIL_CHAIR
            and not obj.is_active
        ):
            # Check whether this WSCC actually has pending reviews
            from teams.models import WardLonglist, WardLonglistStatus
            pending_count = WardLonglist.objects.filter(
                discipline__ward=obj.ward,
                status=WardLonglistStatus.SUBMITTED,
            ).count()
            if pending_count:
                messages.warning(
                    request,
                    f"WSCC deactivated with {pending_count} pending longlist review(s) "
                    f"for ward '{obj.ward}'. These reviews cannot be actioned until a "
                    f"replacement WSCC is assigned to this ward."
                )
            else:
                messages.warning(
                    request,
                    f"WSCC for ward '{obj.ward}' has been deactivated. "
                    f"Any future pending reviews must be manually reassigned to a new WSCC "
                    f"before they can be actioned."
                )

        # Run model-level clean() so the WSCC uniqueness check (and any other
        # model validation) fires through the admin panel as well as through forms.
        try:
            obj.clean()
        except ValidationError:
            raise

        super().save_model(request, obj, form, change)
