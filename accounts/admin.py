from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import PermissionToggle, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (
            "Barber CRM",
            {
                "fields": (
                    "display_name",
                    "role",
                    "preferred_language",
                )
            },
        ),
    )
    list_display = ("username", "display_name", "email", "role", "is_active")
    list_filter = ("role", "is_active", "is_staff", "is_superuser")


@admin.register(PermissionToggle)
class PermissionToggleAdmin(admin.ModelAdmin):
    list_display = ("key", "role", "user", "is_allowed", "updated_by", "updated_at")
    list_filter = ("key", "role", "is_allowed")
    search_fields = ("user__username", "user__display_name")
