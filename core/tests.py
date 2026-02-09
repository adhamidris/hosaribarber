from django.test import TestCase
from django.urls import reverse

from accounts.models import RoleChoices, User


class CoreViewsTests(TestCase):
    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_access_when_logged_in(self):
        user = User.objects.create_user(
            username="dashboarduser",
            password="pass12345",
            role=RoleChoices.OWNER_ADMIN,
        )
        self.client.force_login(user)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
