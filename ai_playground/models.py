import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def _build_session_token() -> str:
    return secrets.token_urlsafe(32)


def _default_session_expiry():
    duration_minutes = int(getattr(settings, "AI_PLAYGROUND_SESSION_DURATION_MINUTES", 30))
    return timezone.now() + timedelta(minutes=duration_minutes)


class PlaygroundStyle(models.Model):
    name = models.CharField(max_length=120, blank=True, null=True)
    description = models.TextField(blank=True, default="")
    image = models.ImageField(upload_to="ai-playground/styles/%Y/%m/%d")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name or "Untitled style"


class PlaygroundBeardStyle(models.Model):
    name = models.CharField(max_length=120, blank=True, null=True)
    image = models.ImageField(upload_to="ai-playground/beard-styles/%Y/%m/%d")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name or "Untitled beard style"


class PlaygroundColorScopeChoices(models.TextChoices):
    HAIR = "hair", _("Hair")
    BEARD = "beard", _("Beard")
    BOTH = "both", _("Hair + Beard")


class PlaygroundColorOption(models.Model):
    name = models.CharField(max_length=64)
    hex_code = models.CharField(max_length=7, default="#111111")
    scope = models.CharField(
        max_length=12,
        choices=PlaygroundColorScopeChoices.choices,
        default=PlaygroundColorScopeChoices.BOTH,
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name


class PlaygroundSession(models.Model):
    token = models.CharField(max_length=64, unique=True, default=_build_session_token)
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=_default_session_expiry, db_index=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    selfie_image = models.ImageField(
        upload_to="ai-playground/session-selfies/%Y/%m/%d",
        null=True,
        blank=True,
    )
    selfie_uploaded_at = models.DateTimeField(null=True, blank=True)
    generation_count = models.PositiveIntegerField(default=0)
    last_generation_at = models.DateTimeField(null=True, blank=True)
    last_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.token[:8]}…"

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and self.expires_at > timezone.now()

    def touch(self, ip_address: str = "", user_agent: str = ""):
        self.last_seen_at = timezone.now()
        if ip_address:
            self.last_ip = ip_address
        if user_agent:
            self.user_agent = user_agent[:255]

    @property
    def has_selfie(self) -> bool:
        return bool(self.selfie_image)


class PlaygroundGenerationStatusChoices(models.TextChoices):
    PENDING = "pending", _("Pending")
    SUCCEEDED = "succeeded", _("Succeeded")
    FAILED = "failed", _("Failed")


class PlaygroundGeneration(models.Model):
    session = models.ForeignKey(
        PlaygroundSession,
        on_delete=models.CASCADE,
        related_name="generations",
    )
    style = models.ForeignKey(
        PlaygroundStyle,
        on_delete=models.SET_NULL,
        related_name="generations",
        null=True,
        blank=True,
    )
    beard_style = models.ForeignKey(
        PlaygroundBeardStyle,
        on_delete=models.SET_NULL,
        related_name="generations",
        null=True,
        blank=True,
    )
    hair_color_option = models.ForeignKey(
        PlaygroundColorOption,
        on_delete=models.SET_NULL,
        related_name="hair_generations",
        null=True,
        blank=True,
    )
    beard_color_option = models.ForeignKey(
        PlaygroundColorOption,
        on_delete=models.SET_NULL,
        related_name="beard_generations",
        null=True,
        blank=True,
    )
    selfie_image = models.ImageField(upload_to="ai-playground/selfies/%Y/%m/%d")
    custom_style_image = models.ImageField(
        upload_to="ai-playground/custom-styles/%Y/%m/%d",
        null=True,
        blank=True,
    )
    custom_style_fingerprint = models.CharField(max_length=64, blank=True, db_index=True)
    result_image = models.ImageField(
        upload_to="ai-playground/results/%Y/%m/%d",
        null=True,
        blank=True,
    )
    provider = models.CharField(max_length=50, blank=True)
    status = models.CharField(
        max_length=16,
        choices=PlaygroundGenerationStatusChoices.choices,
        default=PlaygroundGenerationStatusChoices.PENDING,
    )
    processing_ms = models.PositiveIntegerField(null=True, blank=True)
    error_message = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.session_id} :: {self.status}"


class PlaygroundRateLimitActionChoices(models.TextChoices):
    START = "start", _("Start Session")
    GENERATE = "generate", _("Generate Preview")


class PlaygroundRateLimitEvent(models.Model):
    action = models.CharField(
        max_length=24,
        choices=PlaygroundRateLimitActionChoices.choices,
    )
    ip_address = models.GenericIPAddressField()
    session = models.ForeignKey(
        PlaygroundSession,
        on_delete=models.SET_NULL,
        related_name="rate_limit_events",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action", "ip_address", "created_at"]),
        ]

    def __str__(self):
        return f"{self.action} :: {self.ip_address}"
