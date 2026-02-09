from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import RoleChoices, User
from services.models import Service, ServiceCategoryChoices


class ServiceFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="service-owner",
            password="pass12345",
            role=RoleChoices.OWNER_ADMIN,
        )
        self.client.force_login(self.user)

    def test_service_form_exposes_only_required_fields(self):
        response = self.client.get(reverse("service-create"))
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(list(form.fields.keys()), ["category", "service_name", "price"])

    def test_service_create_with_unified_name_and_price(self):
        response = self.client.post(
            reverse("service-create"),
            {
                "category": ServiceCategoryChoices.HAIR_CARE,
                "service_name": "Premium Cut",
                "price": "250.00",
            },
        )
        self.assertEqual(response.status_code, 302)
        service = Service.objects.get()
        self.assertEqual(service.name_ar, "Premium Cut")
        self.assertEqual(service.name_en, "Premium Cut")
        self.assertEqual(service.price, Decimal("250.00"))

    def test_service_update_keeps_unified_name_shape(self):
        service = Service.objects.create(
            name_ar="قص",
            name_en="Cut",
            category=ServiceCategoryChoices.OTHER,
            price=Decimal("120.00"),
        )
        response = self.client.post(
            reverse("service-update", args=[service.id]),
            {
                "category": ServiceCategoryChoices.SKIN_CARE,
                "service_name": "Facial",
                "price": "300.00",
            },
        )
        self.assertEqual(response.status_code, 302)
        service.refresh_from_db()
        self.assertEqual(service.name_ar, "Facial")
        self.assertEqual(service.name_en, "Facial")
        self.assertEqual(service.category, ServiceCategoryChoices.SKIN_CARE)
        self.assertEqual(service.price, Decimal("300.00"))
