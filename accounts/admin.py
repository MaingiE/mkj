from django import forms
from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.core.exceptions import ValidationError

import json

from .models import User, UserRole, MAKUENI_SUBCOUNTY_WARDS


class UserAdminForm(forms.ModelForm):
    """
    Custom admin form for the User model.

    Extra validations added on top of model-level clean():
    - WSCC must have both ward and sub_county set
    - WSCC's ward must belong to the declared sub_county
      (prevents e.g. assigning Wote ward to Kibwezi West sub-county)
    - Coordinators and scouts must have assigned_discipline
    """

    class Meta:
        model  = User
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        role       = cleaned.get("role", "")
        sub_county = (cleaned.get("sub_county") or "").strip()
        ward       = (cleaned.get("ward") or "").strip()
        is_active  = cleaned.get("is_active", True)

        if role == UserRole.WARD_SPORTS_COUNCIL_CHAIR:
            # Both fields are required for a WSCC
            if not sub_county:
                self.add_error("sub_county", "Sub-county is required for a Ward Sports Council Chair.")
            if not ward:
                self.add_error("ward", "Ward is required for a Ward Sports Council Chair.")

            # Ward must actually belong to the declared sub-county
            if sub_county and ward:
                valid_wards = MAKUENI_SUBCOUNTY_WARDS.get(sub_county, [])
                if valid_wards and ward not in valid_wards:
                    self.add_error(
                        "ward",
                        f'"{ward}" is not a valid ward for {sub_county} sub-county. '
                        f'Valid wards: {", ".join(valid_wards)}.',
                    )

            # Duplicate check (complements the model-level UniqueConstraint)
            if sub_county and ward and is_active:
                pk = self.instance.pk if self.instance else None
                qs = User.objects.filter(
                    role=UserRole.WARD_SPORTS_COUNCIL_CHAIR,
                    is_active=True,
                    ward=ward,
                    sub_county=sub_county,
                )
                if pk:
                    qs = qs.exclude(pk=pk)
                if qs.exists():
                    existing = qs.first()
                    self.add_error(
                        "ward",
                        f"An active WSCC already exists for {ward} ward in "
                        f"{sub_county} sub-county: {existing.get_full_name()} "
                        f"({existing.email}). Deactivate that account first.",
                    )

        if role in ("coordinator", "scout"):
            if not cleaned.get("assigned_discipline"):
                self.add_error("assigned_discipline", "Discipline is required for coordinators and scouts.")

        return cleaned


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserAdminForm

    class Media:
        js = (
            "admin/js/jquery.init.js",
            "admin/wscc_subcounty.js",
        )

    list_display  = [
        "email", "get_full_name", "role", "sub_county", "ward",
        "pending_longlist_count", "is_active", "date_joined",
    ]
    list_filter   = ["role", "county", "sub_county", "ward", "is_active", "is_staff"]
    search_fields = ["email", "first_name", "last_name", "ward", "sub_county"]
    ordering      = ["last_name", "first_name"]

    fieldsets = (
        (None,       {"fields": ("email", "password")}),
        ("Personal", {"fields": ("first_name", "last_name", "phone", "profile_photo")}),
        ("MKJ SUPA CUP Role & Location", {
            "description": (
                "For Ward Sports Council Chair: both sub-county AND ward are required. "
                "The ward must belong to the selected sub-county."
            ),
            "fields": ("role", "county", "sub_county", "ward", "assigned_discipline"),
        }),
        ("Permissions", {"fields": ("is_active", "is_suspended", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates",    {"fields": ("date_joined", "last_login")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "description": (
                "For Ward Sports Council Chair: set sub-county first, then "
                "select the matching ward. Only one active WSCC is allowed per ward per sub-county."
            ),
            "fields": (
                "email", "first_name", "last_name", "phone",
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
        scoped to their assigned ward + sub_county.
        Returns '-' for all other roles.
        """
        if obj.role != UserRole.WARD_SPORTS_COUNCIL_CHAIR or not obj.ward:
            return "-"
        from teams.models import WardLonglist, WardLonglistStatus
        return WardLonglist.objects.filter(
            discipline__ward=obj.ward,
            discipline__sub_county=obj.sub_county,
            status=WardLonglistStatus.SUBMITTED,
        ).count()

    def save_model(self, request, obj, form, change):
        # Deactivation warning: surface pending reviews that need reassignment
        if (
            change
            and obj.role == UserRole.WARD_SPORTS_COUNCIL_CHAIR
            and not obj.is_active
        ):
            from teams.models import WardLonglist, WardLonglistStatus
            pending_count = WardLonglist.objects.filter(
                discipline__ward=obj.ward,
                discipline__sub_county=obj.sub_county,
                status=WardLonglistStatus.SUBMITTED,
            ).count()
            ward_label = f"{obj.ward} ward ({obj.sub_county})"
            if pending_count:
                messages.warning(
                    request,
                    f"WSCC for {ward_label} deactivated with {pending_count} "
                    f"pending longlist review(s). A new WSCC must be assigned "
                    f"to this ward before those reviews can be actioned."
                )
            else:
                messages.warning(
                    request,
                    f"WSCC for {ward_label} has been deactivated. "
                    f"Assign a replacement WSCC for future reviews."
                )

        # Run model-level clean() so UniqueConstraint and clean() both fire
        try:
            obj.clean()
        except ValidationError:
            raise

        super().save_model(request, obj, form, change)

    def get_form(self, request, obj=None, **kwargs):
        """Attach MAKUENI_SUBCOUNTY_WARDS mapping as JSON on the sub_county field
        so the admin JS can populate the ward select dynamically.
        """
        form = super().get_form(request, obj, **kwargs)
        try:
            sc_field = form.base_fields.get("sub_county")
            ward_field = form.base_fields.get("ward")
            if sc_field:
                sc_field.widget.attrs.setdefault("data-wards", json.dumps(MAKUENI_SUBCOUNTY_WARDS))
            if ward_field:
                # Keep a flat list of all wards as a fallback
                ward_field.widget.attrs.setdefault("data-all-wards", json.dumps([w for sc in MAKUENI_SUBCOUNTY_WARDS.values() for w in sc]))
        except Exception:
            # Be defensive; admin should still work even if attaching attrs fails
            pass
        return form
