from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from .forms import ServiceForm
from .models import Service


@login_required
def service_list(request):
    query = request.GET.get("q", "").strip()
    services = Service.objects.all()
    if query:
        services = services.filter(Q(name_ar__icontains=query) | Q(name_en__icontains=query))
    services = services.order_by("name_en")

    return render(
        request,
        "services/service_list.html",
        {
            "services": services,
            "query": query,
        },
    )


@login_required
def service_create(request):
    if request.method == "POST":
        form = ServiceForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("Service created successfully."))
            return redirect("service-list")
    else:
        form = ServiceForm()

    return render(
        request,
        "services/service_form.html",
        {
            "form": form,
            "title": _("New Service"),
        },
    )


@login_required
def service_update(request, service_id):
    service = get_object_or_404(Service, id=service_id)

    if request.method == "POST":
        form = ServiceForm(request.POST, instance=service)
        if form.is_valid():
            form.save()
            messages.success(request, _("Service updated successfully."))
            return redirect("service-list")
    else:
        form = ServiceForm(instance=service)

    return render(
        request,
        "services/service_form.html",
        {
            "form": form,
            "title": _("Edit Service"),
            "service": service,
        },
    )
