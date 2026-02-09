from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from accounts.models import PermissionKeyChoices
from accounts.permissions import has_permission_toggle

from .forms import ClientCommentForm, ClientForm
from .models import Client, ClientComment


def _create_initial_comment_from_general_notes(client, user):
    note = (client.general_notes or "").strip()
    if not note:
        return

    ClientComment.objects.create(
        client=client,
        comment=note[:600],
        created_by=user,
    )


@login_required
def client_list(request):
    query = request.GET.get("q", "").strip()
    clients = Client.objects.all()
    if query:
        clients = clients.filter(Q(full_name__icontains=query) | Q(phone__icontains=query))
    clients = clients.order_by("full_name")

    return render(
        request,
        "clients/client_list.html",
        {
            "clients": clients,
            "query": query,
        },
    )


@login_required
def client_create(request):
    identity_editable = has_permission_toggle(
        request.user,
        PermissionKeyChoices.EDIT_CLIENT_IDENTITY,
        default=True,
    )
    if not identity_editable:
        messages.error(request, _("You do not have permission to create clients."))
        return redirect("client-list")

    if request.method == "POST":
        form = ClientForm(request.POST, identity_editable=identity_editable)
        if form.is_valid():
            client = form.save(commit=False)
            client.created_by = request.user
            client.updated_by = request.user
            client.save()
            _create_initial_comment_from_general_notes(client, request.user)
            messages.success(request, _("Client created successfully."))
            return redirect("client-detail", client_id=client.id)
    else:
        form = ClientForm(identity_editable=identity_editable)

    return render(
        request,
        "clients/client_form.html",
        {
            "form": form,
            "title": _("New Client"),
            "identity_editable": identity_editable,
        },
    )


@login_required
def client_detail(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    comments = client.comments.select_related("created_by").all()
    comment_form = ClientCommentForm()

    return render(
        request,
        "clients/client_detail.html",
        {
            "client": client,
            "comments": comments,
            "comment_form": comment_form,
        },
    )


@login_required
def client_lookup_by_phone(request):
    phone = (request.GET.get("phone") or "").strip()
    if not phone:
        return JsonResponse({"exists": False})

    client = Client.objects.filter(phone=phone).values("id", "full_name").first()
    if not client:
        return JsonResponse({"exists": False})

    return JsonResponse(
        {
            "exists": True,
            "id": client["id"],
            "full_name": client["full_name"],
        }
    )


@login_required
@require_POST
def client_comment_create(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    form = ClientCommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.client = client
        comment.created_by = request.user
        comment.save()
        messages.success(request, _("Comment added successfully."))
    else:
        messages.error(request, _("Comment could not be added."))
    return redirect(f"{reverse('client-detail', args=[client.id])}#client-comments")


@login_required
def client_update(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    identity_editable = has_permission_toggle(
        request.user,
        PermissionKeyChoices.EDIT_CLIENT_IDENTITY,
        default=True,
    )

    if request.method == "POST":
        form = ClientForm(request.POST, instance=client, identity_editable=identity_editable)
        if form.is_valid():
            updated_client = form.save(commit=False)
            if not identity_editable:
                updated_client.full_name = client.full_name
                updated_client.phone = client.phone
                updated_client.date_of_birth = client.date_of_birth
            updated_client.updated_by = request.user
            updated_client.save()
            messages.success(request, _("Client updated successfully."))
            return redirect("client-detail", client_id=client.id)
    else:
        form = ClientForm(instance=client, identity_editable=identity_editable)

    if not identity_editable:
        messages.warning(request, _("Identity fields are locked by owner permission settings."))

    return render(
        request,
        "clients/client_form.html",
        {
            "form": form,
            "title": _("Edit Client"),
            "client": client,
            "identity_editable": identity_editable,
        },
    )
