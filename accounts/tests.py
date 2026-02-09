from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from .models import PermissionKeyChoices, PermissionToggle, RoleChoices, User
from .permissions import has_permission_toggle


class PermissionToggleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="barber1",
            password="pass12345",
            role=RoleChoices.BARBER,
        )

    def test_returns_default_when_no_toggle(self):
        self.assertTrue(has_permission_toggle(self.user, PermissionKeyChoices.EDIT_CLIENT_IDENTITY))

    def test_role_toggle_overrides_default(self):
        PermissionToggle.objects.create(
            key=PermissionKeyChoices.EDIT_CLIENT_IDENTITY,
            role=RoleChoices.BARBER,
            is_allowed=False,
        )
        self.assertFalse(has_permission_toggle(self.user, PermissionKeyChoices.EDIT_CLIENT_IDENTITY))

    def test_user_toggle_overrides_role_toggle(self):
        PermissionToggle.objects.create(
            key=PermissionKeyChoices.EDIT_CLIENT_IDENTITY,
            role=RoleChoices.BARBER,
            is_allowed=False,
        )
        PermissionToggle.objects.create(
            key=PermissionKeyChoices.EDIT_CLIENT_IDENTITY,
            user=self.user,
            is_allowed=True,
        )
        self.assertTrue(has_permission_toggle(self.user, PermissionKeyChoices.EDIT_CLIENT_IDENTITY))


class LanguageSwitchTests(TestCase):
    def setUp(self):
        translation.activate("ar")
        self.user = User.objects.create_user(
            username="lang-user",
            password="pass12345",
            role=RoleChoices.OWNER_ADMIN,
        )
        self.client.force_login(self.user)

    def tearDown(self):
        translation.deactivate_all()

    def test_switch_to_english_redirects_to_prefixed_url(self):
        response = self.client.post(
            reverse("switch-language"),
            {
                "language": "en",
                "next": reverse("dashboard"),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/en/dashboard/")
        self.user.refresh_from_db()
        self.assertEqual(self.user.preferred_language, "en")

    def test_switch_back_to_arabic_redirects_to_unprefixed_url(self):
        self.user.preferred_language = "en"
        self.user.save(update_fields=["preferred_language"])

        with translation.override("en"):
            switch_url = reverse("switch-language")

        response = self.client.post(
            switch_url,
            {
                "language": "ar",
                "next": "/en/dashboard/",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/dashboard/")
        self.user.refresh_from_db()
        self.assertEqual(self.user.preferred_language, "ar")

    def test_non_prefixed_page_auto_redirects_for_english_user(self):
        self.user.preferred_language = "en"
        self.user.save(update_fields=["preferred_language"])

        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/en/dashboard/")
