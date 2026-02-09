from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from appointments.models import Appointment
from clients.models import Client
from services.models import Service


def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return redirect("login")


@login_required
def dashboard(request):
    today = timezone.localdate()
    appointment_count = Appointment.objects.filter(start_at__date=today).count()
    walk_in_count = Appointment.objects.filter(start_at__date=today, is_walk_in=True).count()
    context = {
        "client_count": Client.objects.count(),
        "service_count": Service.objects.filter(is_active=True).count(),
        "appointment_count": appointment_count,
        "walk_in_count": walk_in_count,
    }
    return render(request, "core/dashboard.html", context)
