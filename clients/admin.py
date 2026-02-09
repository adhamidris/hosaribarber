from django.contrib import admin

from .models import Client, ClientComment


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "gender", "marketing_opt_in", "updated_at")
    list_filter = ("gender", "marketing_opt_in", "photo_marketing_opt_in")
    search_fields = ("full_name", "phone", "email")


@admin.register(ClientComment)
class ClientCommentAdmin(admin.ModelAdmin):
    list_display = ("client", "created_by", "created_at")
    list_filter = ("created_at",)
    search_fields = ("client__full_name", "client__phone", "comment")
