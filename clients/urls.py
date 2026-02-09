from django.urls import path

from .views import (
    client_comment_create,
    client_create,
    client_detail,
    client_lookup_by_phone,
    client_list,
    client_update,
)

urlpatterns = [
    path("clients/", client_list, name="client-list"),
    path("clients/new/", client_create, name="client-create"),
    path("clients/lookup-by-phone/", client_lookup_by_phone, name="client-lookup-by-phone"),
    path("clients/<int:client_id>/", client_detail, name="client-detail"),
    path("clients/<int:client_id>/comments/add/", client_comment_create, name="client-comment-create"),
    path("clients/<int:client_id>/edit/", client_update, name="client-update"),
]
