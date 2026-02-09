from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "content_type", "object_id", "actor", "created_at")
    list_filter = ("action", "content_type")
    search_fields = ("object_id", "actor__username")
    readonly_fields = ("content_type", "object_id", "action", "changed_fields", "actor", "created_at")
