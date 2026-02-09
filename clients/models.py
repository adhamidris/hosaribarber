from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class GenderChoices(models.TextChoices):
    MALE = "male", _("Male")
    FEMALE = "female", _("Female")
    OTHER = "other", _("Other")
    PREFER_NOT_TO_SAY = "prefer_not_to_say", _("Prefer not to say")


class Client(models.Model):
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=30, unique=True)
    email = models.EmailField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=24, choices=GenderChoices.choices, blank=True)
    preferred_drink = models.CharField(max_length=120, blank=True)
    general_notes = models.TextField(blank=True)
    marketing_opt_in = models.BooleanField(default=False)
    photo_marketing_opt_in = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_clients",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_clients",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]
        indexes = [
            models.Index(fields=["phone"]),
            models.Index(fields=["full_name"]),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.phone})"


class ClientComment(models.Model):
    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.CASCADE,
        related_name="comments",
    )
    comment = models.TextField(max_length=600)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="client_comments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["client", "created_at"]),
        ]

    def __str__(self):
        return f"{self.client.full_name}: {self.comment[:50]}"
