from django.test import TestCase
from django.urls import reverse

from accounts.models import RoleChoices, User

from .models import Client, ClientComment


class ClientCreateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="reception1",
            password="pass12345",
            role=RoleChoices.RECEPTIONIST,
        )
        self.client.force_login(self.user)

    def test_client_create_turns_general_notes_into_comment(self):
        response = self.client.post(
            reverse("client-create"),
            {
                "full_name": "Mohamed Samir",
                "phone": "01111111111",
                "email": "",
                "date_of_birth": "",
                "gender": "",
                "preferred_drink": "",
                "general_notes": "Prefers no strong fragrance.",
                "marketing_opt_in": "",
                "photo_marketing_opt_in": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Client.objects.filter(phone="01111111111").count(), 1)
        created_client = Client.objects.get(phone="01111111111")
        self.assertEqual(created_client.comments.count(), 1)
        self.assertEqual(created_client.comments.get().comment, "Prefers no strong fragrance.")

    def test_client_update_changes_name(self):
        client = Client.objects.create(
            full_name="Initial Name",
            phone="01234567890",
            created_by=self.user,
            updated_by=self.user,
        )

        response = self.client.post(
            reverse("client-update", args=[client.id]),
            {
                "full_name": "Updated Name",
                "phone": client.phone,
                "email": "",
                "date_of_birth": "",
                "gender": "",
                "preferred_drink": "",
                "general_notes": "",
                "marketing_opt_in": "",
                "photo_marketing_opt_in": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        client.refresh_from_db()
        self.assertEqual(client.full_name, "Updated Name")


class ClientCommentsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="barber-comments",
            password="pass12345",
            role=RoleChoices.BARBER,
        )
        self.client.force_login(self.user)
        self.customer = Client.objects.create(
            full_name="Comment Target",
            phone="01000000000",
            created_by=self.user,
            updated_by=self.user,
        )

    def test_add_client_comment_creates_new_comment(self):
        response = self.client.post(
            reverse("client-comment-create", args=[self.customer.id]),
            {"comment": "Prefers side-part and short fade."},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ClientComment.objects.filter(client=self.customer).count(), 1)
        comment = ClientComment.objects.get(client=self.customer)
        self.assertEqual(comment.comment, "Prefers side-part and short fade.")
        self.assertEqual(comment.created_by, self.user)

    def test_client_detail_shows_comments(self):
        ClientComment.objects.create(
            client=self.customer,
            comment="Allergic to strong fragrance products.",
            created_by=self.user,
        )
        response = self.client.get(reverse("client-detail", args=[self.customer.id]))
        self.assertContains(response, "General comments")
        self.assertContains(response, "Allergic to strong fragrance products.")


class ClientLookupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="reception-lookup",
            password="pass12345",
            role=RoleChoices.RECEPTIONIST,
        )
        self.client.force_login(self.user)
        self.customer = Client.objects.create(
            full_name="Lookup Target",
            phone="01012345678",
            created_by=self.user,
            updated_by=self.user,
        )

    def test_client_lookup_by_phone_finds_existing_client(self):
        response = self.client.get(reverse("client-lookup-by-phone"), {"phone": self.customer.phone})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["exists"])
        self.assertEqual(payload["id"], self.customer.id)
        self.assertEqual(payload["full_name"], "Lookup Target")

    def test_client_lookup_by_phone_returns_not_found(self):
        response = self.client.get(reverse("client-lookup-by-phone"), {"phone": "09999999999"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["exists"])
