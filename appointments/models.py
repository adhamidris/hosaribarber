from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class AppointmentStatusChoices(models.TextChoices):
    SCHEDULED = "scheduled", _("Scheduled")
    CONFIRMED = "confirmed", _("Confirmed")
    COMPLETED = "completed", _("Completed")
    CANCELLED = "cancelled", _("Cancelled")
    NO_SHOW = "no_show", _("No Show")


class Appointment(models.Model):
    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.CASCADE,
        related_name="appointments",
    )
    barber = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments",
    )
    service = models.ForeignKey(
        "services.Service",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments",
    )
    services = models.ManyToManyField(
        "services.Service",
        blank=True,
        related_name="appointments_multi",
    )
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    status = models.CharField(
        max_length=24,
        choices=AppointmentStatusChoices.choices,
        default=AppointmentStatusChoices.SCHEDULED,
    )
    is_walk_in = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_appointments",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_appointments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_at"]
        indexes = [
            models.Index(fields=["start_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["barber", "start_at"]),
        ]

    def clean(self):
        if self.start_at and self.end_at and self.end_at <= self.start_at:
            raise ValidationError(_("Appointment end time must be after start time."))

    def selected_services(self):
        items = list(self.services.all())
        if items:
            return items
        if self.service_id:
            return [self.service]
        return []

    def services_display(self):
        items = self.selected_services()
        if not items:
            return "-"
        return ", ".join(str(item) for item in items)

    def __str__(self):
        return f"{self.client} :: {self.start_at:%Y-%m-%d %H:%M}"
