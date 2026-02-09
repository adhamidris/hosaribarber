from django.contrib import admin

from .models import (
    PlaygroundGeneration,
    PlaygroundRateLimitEvent,
    PlaygroundSession,
    PlaygroundStyle,
)


@admin.register(PlaygroundStyle)
class PlaygroundStyleAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "sort_order", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("sort_order", "id")


@admin.register(PlaygroundSession)
class PlaygroundSessionAdmin(admin.ModelAdmin):
    list_display = (
        "short_token",
        "started_at",
        "expires_at",
        "revoked_at",
        "has_selfie",
        "generation_count",
        "last_generation_at",
        "last_ip",
    )
    list_filter = ("revoked_at",)
    search_fields = ("token", "last_ip", "user_agent")
    readonly_fields = ("token", "started_at", "last_seen_at")
    ordering = ("-started_at",)

    @staticmethod
    def short_token(obj: PlaygroundSession) -> str:
        return f"{obj.token[:8]}…"

    @staticmethod
    def has_selfie(obj: PlaygroundSession) -> bool:
        return obj.has_selfie


@admin.register(PlaygroundGeneration)
class PlaygroundGenerationAdmin(admin.ModelAdmin):
    list_display = ("id", "session_id", "status", "provider", "created_at")
    list_filter = ("status", "provider")
    search_fields = ("id", "session__token", "error_message")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(PlaygroundRateLimitEvent)
class PlaygroundRateLimitEventAdmin(admin.ModelAdmin):
    list_display = ("action", "ip_address", "session_id", "created_at")
    list_filter = ("action",)
    search_fields = ("ip_address", "session__token")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
