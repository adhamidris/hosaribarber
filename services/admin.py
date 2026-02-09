from django.contrib import admin

from .models import Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name_en", "category", "price", "is_active")
    list_filter = ("category",)
    search_fields = ("name_ar", "name_en")
