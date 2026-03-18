from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display  = ["email", "get_full_name", "role", "county", "is_active", "date_joined"]
    list_filter   = ["role", "county", "is_active", "is_staff"]
    search_fields = ["email", "first_name", "last_name"]
    ordering      = ["last_name", "first_name"]

    fieldsets = (
        (None,        {"fields": ("email", "password")}),
        ("Personal",  {"fields": ("first_name", "last_name", "phone", "profile_photo")}),
        ("MKJ SUPA CUP",     {"fields": ("role", "county")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates",     {"fields": ("date_joined", "last_login")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "first_name", "last_name", "role", "county", "password1", "password2"),
        }),
    )
    readonly_fields = ["date_joined", "last_login"]
