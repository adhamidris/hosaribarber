from django.urls import path

from .views import (
    appointment_list,
    appointment_update,
)

urlpatterns = [
    path("appointments/", appointment_list, name="appointment-list"),
    path("appointments/<int:appointment_id>/edit/", appointment_update, name="appointment-update"),
]
