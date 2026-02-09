from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import get_language, gettext_lazy as _


class ServiceCategoryChoices(models.TextChoices):
    HAIR_CARE = "hair_care", _("Hair Care")
    SKIN_CARE = "skin_care", _("Skin Care")
    BARBER_SERVICES = "barber_services", _("Barber Services")
    OTHER = "other", _("Other")


class Service(models.Model):
    name_ar = models.CharField(max_length=120)
    name_en = models.CharField(max_length=120)
    category = models.CharField(
        max_length=32,
        choices=ServiceCategoryChoices.choices,
        default=ServiceCategoryChoices.OTHER,
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    default_duration_minutes = models.PositiveIntegerField(
        default=30,
        validators=[MinValueValidator(1)],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name_en"]

    def __str__(self):
        language_code = get_language() or "ar"
        if language_code.startswith("ar"):
            return self.name_ar
        return self.name_en
