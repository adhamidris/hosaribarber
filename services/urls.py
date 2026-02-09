from django.urls import path

from .views import service_create, service_list, service_update

urlpatterns = [
    path("services/", service_list, name="service-list"),
    path("services/new/", service_create, name="service-create"),
    path("services/<int:service_id>/edit/", service_update, name="service-update"),
]
