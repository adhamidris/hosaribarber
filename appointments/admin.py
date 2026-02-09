from django.contrib import admin

from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("client", "barber", "services_summary", "total_price", "start_at", "end_at", "status", "is_walk_in")
    list_filter = ("status", "is_walk_in")
    search_fields = ("client__full_name", "client__phone", "barber__username")

    @admin.display(description="Services")
    def services_summary(self, obj):
        return obj.services_display()
