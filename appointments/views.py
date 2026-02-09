from datetime import datetime, time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from accounts.models import PermissionKeyChoices
from accounts.permissions import has_permission_toggle

from .forms import AppointmentEntryForm, AppointmentForm
from .models import Appointment


def _get_scope(scope_param):
    if scope_param in {"today_queue", "all_history", "upcoming_7_days", "upcoming_month"}:
        return scope_param
    return "today_queue"


def _get_entry_type(entry_type_param):
    if entry_type_param in {"all", "booking", "walk_in"}:
        return entry_type_param
    return "all"


def _normalize_services_payload(payload):
    normalized = payload.copy()
    if hasattr(normalized, "getlist"):
        if not normalized.getlist("services") and normalized.get("service"):
            normalized.setlist("services", [normalized.get("service")])
    elif not normalized.get("services") and normalized.get("service"):
        normalized["services"] = normalized.get("service")
    return normalized


def _normalize_entry_payload(payload):
    normalized = _normalize_services_payload(payload)
    if normalized.get("classification"):
        return normalized

    legacy_form_type = normalized.get("form_type")
    if legacy_form_type == "walkin":
        normalized["classification"] = "walk_in"
    else:
        normalized["classification"] = "booking"
    return normalized


def _selected_service_ids(form):
    if form is None:
        return set()
    if form.is_bound:
        return {str(value) for value in form.data.getlist("services")}

    initial_services = form.initial.get("services") if hasattr(form, "initial") else None
    if not initial_services:
        return set()
    if hasattr(initial_services, "values_list"):
        return {str(value) for value in initial_services.values_list("id", flat=True)}
    return {str(getattr(value, "id", value)) for value in initial_services}


@login_required
def appointment_list(request):
    scope = _get_scope(request.GET.get("scope", "").strip())
    entry_type = _get_entry_type(request.GET.get("entry_type", "").strip())
    query = request.GET.get("q", "").strip()
    now = timezone.now()
    today = timezone.localdate()
    day_start = timezone.make_aware(datetime.combine(today, time.min))
    day_end = timezone.make_aware(datetime.combine(today, time.max))
    next_7_days_end = timezone.make_aware(datetime.combine(today + timezone.timedelta(days=6), time.max))
    next_month_end = timezone.make_aware(datetime.combine(today + timezone.timedelta(days=29), time.max))

    appointments = (
        Appointment.objects.select_related("client", "barber", "service")
        .prefetch_related("services")
    )
    if scope == "today_queue":
        appointments = appointments.filter(start_at__gte=day_start, start_at__lte=day_end)
    elif scope == "upcoming_7_days":
        appointments = appointments.filter(
            start_at__gte=now,
            start_at__lte=next_7_days_end,
            is_walk_in=False,
        )
        entry_type = "booking"
    elif scope == "upcoming_month":
        appointments = appointments.filter(
            start_at__gte=now,
            start_at__lte=next_month_end,
            is_walk_in=False,
        )
        entry_type = "booking"

    if scope in {"today_queue", "all_history"}:
        if entry_type == "booking":
            appointments = appointments.filter(is_walk_in=False)
        elif entry_type == "walk_in":
            appointments = appointments.filter(is_walk_in=True)
    if query:
        appointments = appointments.filter(
            Q(client__full_name__icontains=query)
            | Q(client__phone__icontains=query)
            | Q(barber__username__icontains=query)
        )
    if scope == "today_queue":
        appointments = appointments.order_by("is_walk_in", "start_at")
    elif scope in {"upcoming_7_days", "upcoming_month"}:
        appointments = appointments.order_by("start_at")
    else:
        appointments = appointments.order_by("-start_at")
    appointments = list(appointments)

    if request.method == "POST":
        entry_form = AppointmentEntryForm(_normalize_entry_payload(request.POST))
        if entry_form.is_valid():
            can_edit_client_identity = has_permission_toggle(
                request.user,
                PermissionKeyChoices.EDIT_CLIENT_IDENTITY,
                default=True,
            )
            appointment = entry_form.save(
                actor=request.user,
                can_edit_client_identity=can_edit_client_identity,
            )
            if appointment.is_walk_in:
                messages.success(request, _("Walk-in created successfully."))
            else:
                messages.success(request, _("Appointment created successfully."))
            return redirect("appointment-list")
    else:
        entry_form = AppointmentEntryForm(
            initial={
                "classification": "booking",
                "start_at": timezone.localtime().replace(second=0, microsecond=0),
            }
        )
    selected_service_ids = _selected_service_ids(entry_form)
    grouped_services = entry_form.get_grouped_services(selected_ids=selected_service_ids)

    return render(
        request,
        "appointments/appointment_list.html",
        {
            "appointments": appointments,
            "query": query,
            "scope": scope,
            "entry_type": entry_type,
            "entry_form": entry_form,
            "show_entry_modal": request.method == "POST" and bool(entry_form.errors),
            "client_lookup_url": reverse("client-lookup-by-phone"),
            "selected_service_ids": selected_service_ids,
            "grouped_services": grouped_services,
            "default_currency": getattr(settings, "DEFAULT_CURRENCY", ""),
        },
    )


@login_required
def appointment_update(request, appointment_id):
    appointment = get_object_or_404(
        Appointment.objects.select_related("client", "barber", "service").prefetch_related("services"),
        id=appointment_id,
    )

    if request.method == "POST":
        form = AppointmentForm(_normalize_services_payload(request.POST), instance=appointment)
        if form.is_valid():
            updated_appointment = form.save(commit=False)
            updated_appointment.updated_by = request.user
            updated_appointment.save()
            form.save_m2m()
            messages.success(request, _("Appointment updated successfully."))
            return redirect("appointment-list")
    else:
        form = AppointmentForm(instance=appointment)

    return render(
        request,
        "appointments/appointment_form.html",
        {
            "appointment": appointment,
            "form": form,
            "title": _("Edit Appointment"),
        },
    )
