from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Client, ClientComment


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            "full_name",
            "phone",
            "email",
            "date_of_birth",
            "gender",
            "preferred_drink",
            "general_notes",
            "marketing_opt_in",
            "photo_marketing_opt_in",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "general_notes": forms.Textarea(attrs={"rows": 4}),
        }
        labels = {
            "marketing_opt_in": _("Marketing consent"),
            "photo_marketing_opt_in": _("Photo marketing consent"),
        }

    def __init__(self, *args, identity_editable=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.identity_editable = identity_editable
        if not identity_editable:
            for field_name in ("full_name", "phone", "date_of_birth"):
                self.fields[field_name].disabled = True


class ClientCommentForm(forms.ModelForm):
    class Meta:
        model = ClientComment
        fields = ["comment"]
        widgets = {
            "comment": forms.Textarea(
                attrs={
                    "rows": 2,
                    "placeholder": _("Add a quick comment about this client"),
                }
            ),
        }
        labels = {
            "comment": _("Comment"),
        }

    def clean_comment(self):
        value = (self.cleaned_data.get("comment") or "").strip()
        if not value:
            raise forms.ValidationError(_("Comment cannot be empty."))
        return value
