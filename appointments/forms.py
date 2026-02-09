from datetime import timedelta
from decimal import Decimal

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from accounts.models import RoleChoices, User
from clients.models import Client
from services.models import Service, ServiceCategoryChoices

from .models import Appointment, AppointmentStatusChoices


def _calculate_services_totals(services):
    selected_services = list(services or [])
    total_price = sum(((service.price or Decimal("0")) for service in selected_services), Decimal("0"))
    total_duration_minutes = sum((service.default_duration_minutes or 0) for service in selected_services)
    primary_service = selected_services[0] if selected_services else None
    return total_price, total_duration_minutes, primary_service


class BaseAppointmentForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["barber"].queryset = User.objects.filter(role=RoleChoices.BARBER, is_active=True).order_by(
            "display_name",
            "username",
        )
        services_queryset = Service.objects.filter(is_active=True).order_by("category", "name_en", "name_ar")
        if "service" in self.fields:
            self.fields["service"].queryset = services_queryset
        if "services" in self.fields:
            self.fields["services"].queryset = services_queryset
        for field_name in ("start_at", "end_at"):
            if field_name not in self.fields:
                continue
            self.fields[field_name].input_formats = ["%Y-%m-%dT%H:%M"]
            if self.initial.get(field_name):
                self.initial[field_name] = timezone.localtime(self.initial[field_name]).strftime("%Y-%m-%dT%H:%M")


class AppointmentEntryForm(forms.Form):
    classification = forms.ChoiceField(
        choices=(
            ("booking", _("Booking")),
            ("walk_in", _("Walk-in")),
        ),
        initial="booking",
        label=_("Classification"),
    )
    full_name = forms.CharField(max_length=255, required=False)
    phone = forms.CharField(max_length=30, required=False)
    barber = forms.ModelChoiceField(queryset=User.objects.none(), required=False)
    services = forms.ModelMultipleChoiceField(
        queryset=Service.objects.none(),
        required=False,
        label=_("Services"),
        widget=forms.CheckboxSelectMultiple,
    )
    start_at = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        label=_("Booking date"),
    )
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["barber"].queryset = User.objects.filter(role=RoleChoices.BARBER, is_active=True).order_by(
            "display_name",
            "username",
        )
        self.fields["services"].queryset = Service.objects.filter(is_active=True).order_by("category", "name_en", "name_ar")
        if self.initial.get("start_at"):
            self.initial["start_at"] = timezone.localtime(self.initial["start_at"]).strftime("%Y-%m-%dT%H:%M")

    def get_grouped_services(self, *, selected_ids=None):
        selected_values = set(selected_ids or [])
        grouped = []
        grouped_by_key = {}
        category_labels = dict(ServiceCategoryChoices.choices)

        for category_key, category_label in ServiceCategoryChoices.choices:
            bucket = {
                "key": category_key,
                "label": category_labels.get(category_key, category_label),
                "services": [],
                "expanded": False,
            }
            grouped.append(bucket)
            grouped_by_key[category_key] = bucket

        for service in self.fields["services"].queryset:
            category_key = service.category or ServiceCategoryChoices.OTHER
            bucket = grouped_by_key.get(category_key)
            if bucket is None:
                bucket = {
                    "key": category_key,
                    "label": category_key,
                    "services": [],
                    "expanded": False,
                }
                grouped.append(bucket)
                grouped_by_key[category_key] = bucket
            bucket["services"].append(service)
            if str(service.id) in selected_values:
                bucket["expanded"] = True

        return [bucket for bucket in grouped if bucket["services"]]

    def clean_phone(self):
        return (self.cleaned_data.get("phone") or "").strip()

    def clean_full_name(self):
        return (self.cleaned_data.get("full_name") or "").strip()

    def clean(self):
        cleaned_data = super().clean()
        classification = cleaned_data.get("classification")
        phone = cleaned_data.get("phone")
        full_name = cleaned_data.get("full_name")
        services = cleaned_data.get("services")
        existing_client = Client.objects.filter(phone=phone).first() if phone else None

        if classification == "booking":
            if not phone:
                self.add_error("phone", _("Phone is required for booking."))
            if not cleaned_data.get("start_at"):
                self.add_error("start_at", _("Booking date is required for booking."))
            if not full_name:
                if existing_client:
                    cleaned_data["full_name"] = existing_client.full_name
                else:
                    self.add_error("full_name", _("Full name is required for new phone numbers."))
        elif classification == "walk_in":
            if not phone:
                self.add_error("phone", _("Phone is required for walk-in."))
            if not full_name:
                if existing_client:
                    cleaned_data["full_name"] = existing_client.full_name
                else:
                    self.add_error("full_name", _("Full name is required for walk-in."))
        else:
            self.add_error("classification", _("Invalid classification."))

        if not services:
            self.add_error("services", _("Select at least one service."))

        return cleaned_data

    def save(self, *, actor=None, can_edit_client_identity=True):
        classification = self.cleaned_data["classification"]
        full_name = self.cleaned_data["full_name"]
        phone = self.cleaned_data["phone"]
        selected_services = list(self.cleaned_data.get("services") or [])
        barber = self.cleaned_data.get("barber")
        notes = self.cleaned_data.get("notes", "")

        if classification == "booking":
            start_at = self.cleaned_data["start_at"]
            is_walk_in = False
        else:
            start_at = timezone.now()
            is_walk_in = True
        total_price, duration_minutes, primary_service = _calculate_services_totals(selected_services)
        if duration_minutes <= 0:
            duration_minutes = 30

        client_defaults = {"full_name": full_name}
        if actor and actor.is_authenticated:
            client_defaults["created_by"] = actor
            client_defaults["updated_by"] = actor

        client, created = Client.objects.get_or_create(phone=phone, defaults=client_defaults)
        if not created and can_edit_client_identity and client.full_name != full_name:
            client.full_name = full_name
            client.updated_by = actor if actor and actor.is_authenticated else client.updated_by
            client.save(update_fields=["full_name", "updated_by", "updated_at"])

        end_at = start_at + timedelta(minutes=duration_minutes)
        appointment = Appointment.objects.create(
            client=client,
            barber=barber,
            service=primary_service,
            start_at=start_at,
            end_at=end_at,
            total_price=total_price,
            status=AppointmentStatusChoices.SCHEDULED,
            is_walk_in=is_walk_in,
            notes=notes,
            created_by=actor if actor and actor.is_authenticated else None,
            updated_by=actor if actor and actor.is_authenticated else None,
        )
        appointment.services.set(selected_services)
        return appointment


class AppointmentForm(BaseAppointmentForm):
    services = forms.ModelMultipleChoiceField(
        queryset=Service.objects.none(),
        required=False,
        label=_("Services"),
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Appointment
        fields = [
            "client",
            "barber",
            "services",
            "start_at",
            "end_at",
            "status",
            "notes",
        ]
        widgets = {
            "start_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and not self.is_bound:
            existing_services = list(self.instance.services.values_list("id", flat=True))
            if not existing_services and self.instance.service_id:
                existing_services = [self.instance.service_id]
            self.fields["services"].initial = existing_services

    def save(self, commit=True):
        appointment = super().save(commit=False)
        selected_services = list(self.cleaned_data.get("services") or [])
        total_price, _total_duration_minutes, primary_service = _calculate_services_totals(selected_services)
        appointment.total_price = total_price
        appointment.service = primary_service
        if commit:
            appointment.save()
            self.save_m2m()
        return appointment
