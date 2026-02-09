from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class RoleChoices(models.TextChoices):
    OWNER_ADMIN = "owner_admin", _("Owner/Admin")
    RECEPTIONIST = "receptionist", _("Receptionist")
    BARBER = "barber", _("Barber")


class PermissionKeyChoices(models.TextChoices):
    EDIT_CLIENT_IDENTITY = "edit_client_identity", _("Edit client identity fields")
    EXPORT_CAMPAIGNS = "export_campaigns", _("Export campaign lists")


class User(AbstractUser):
    display_name = models.CharField(max_length=150, blank=True)
    preferred_language = models.CharField(
        max_length=8,
        choices=[("ar", _("Arabic")), ("en", _("English"))],
        default="ar",
    )
    role = models.CharField(
        max_length=32,
        choices=RoleChoices.choices,
        default=RoleChoices.BARBER,
    )

    def __str__(self):
        return self.display_name or self.get_full_name() or self.username


class PermissionToggle(models.Model):
    key = models.CharField(max_length=64, choices=PermissionKeyChoices.choices)
    role = models.CharField(
        max_length=32,
        choices=RoleChoices.choices,
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="permission_toggles",
    )
    is_allowed = models.BooleanField(default=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_permission_toggles",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    (Q(role__isnull=False) & Q(user__isnull=True))
                    | (Q(role__isnull=True) & Q(user__isnull=False))
                ),
                name="permission_toggle_exactly_one_target",
            ),
            models.UniqueConstraint(
                fields=["key", "role"],
                condition=Q(user__isnull=True),
                name="permission_toggle_unique_per_role",
            ),
            models.UniqueConstraint(
                fields=["key", "user"],
                condition=Q(user__isnull=False),
                name="permission_toggle_unique_per_user",
            ),
        ]

    def __str__(self):
        if self.user_id:
            return f"{self.key} :: user #{self.user_id}"
        return f"{self.key} :: role {self.role}"
