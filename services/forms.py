from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Service


class ServiceForm(forms.ModelForm):
    service_name = forms.CharField(
        max_length=120,
        label=_("Service Name"),
    )

    class Meta:
        model = Service
        fields = ["category", "price"]
        labels = {
            "category": _("Category"),
            "price": _("Price"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["service_name"].initial = self.instance.name_ar or self.instance.name_en
        self.order_fields(["category", "service_name", "price"])

    def clean_service_name(self):
        value = (self.cleaned_data.get("service_name") or "").strip()
        if not value:
            raise forms.ValidationError(_("Service name is required."))
        return value

    def save(self, commit=True):
        service = super().save(commit=False)
        unified_name = self.cleaned_data["service_name"]
        service.name_ar = unified_name
        service.name_en = unified_name
        if commit:
            service.save()
            self.save_m2m()
        return service
