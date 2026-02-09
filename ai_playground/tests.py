from datetime import timedelta

from django.core import signing
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    PlaygroundGeneration,
    PlaygroundRateLimitActionChoices,
    PlaygroundRateLimitEvent,
    PlaygroundSession,
    PlaygroundStyle,
)
from .views import SESSION_COOKIE_NAME, SESSION_COOKIE_SALT


@override_settings(MEDIA_ROOT="/tmp/ai-playground-tests", AI_PLAYGROUND_PROVIDER="stub")
class PlaygroundSessionTests(TestCase):
    def test_home_requires_active_session(self):
        response = self.client.get(reverse("ai-playground-home"))
        self.assertEqual(response.status_code, 401)
        self.assertContains(response, "Session expired or missing", status_code=401)

    def test_start_route_creates_session_and_cookie(self):
        response = self.client.get(reverse("ai-playground-start"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("ai-playground-home"))
        self.assertEqual(PlaygroundSession.objects.count(), 1)
        self.assertIn(SESSION_COOKIE_NAME, response.cookies)

    @override_settings(AI_PLAYGROUND_START_MAX_PER_IP_PER_HOUR=1)
    def test_start_route_is_rate_limited_per_ip(self):
        first = self.client.get(reverse("ai-playground-start"), REMOTE_ADDR="10.10.0.1")
        self.assertEqual(first.status_code, 302)

        second = self.client.get(reverse("ai-playground-start"), REMOTE_ADDR="10.10.0.1")
        self.assertEqual(second.status_code, 429)
        payload = second.json()
        self.assertFalse(payload["ok"])
        self.assertIn("Too many session starts", payload["error"])

    def test_home_is_accessible_after_start(self):
        start_response = self.client.get(reverse("ai-playground-start"))
        self.assertEqual(start_response.status_code, 302)

        home_response = self.client.get(reverse("ai-playground-home"))
        self.assertEqual(home_response.status_code, 200)
        self.assertContains(home_response, "Step 1")

    def test_expired_session_is_rejected(self):
        session = PlaygroundSession.objects.create(
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.client.cookies[SESSION_COOKIE_NAME] = signing.dumps(session.token, salt=SESSION_COOKIE_SALT)

        response = self.client.get(reverse("ai-playground-home"))
        self.assertEqual(response.status_code, 401)
        self.assertContains(response, "Session expired or missing", status_code=401)


@override_settings(MEDIA_ROOT="/tmp/ai-playground-tests", AI_PLAYGROUND_PROVIDER="stub")
class PlaygroundApiTests(TestCase):
    def setUp(self):
        style_image = SimpleUploadedFile("style.jpg", b"fake-image-content", content_type="image/jpeg")
        self.active_style = PlaygroundStyle.objects.create(
            name="Classic Fade",
            image=style_image,
            is_active=True,
            sort_order=1,
        )
        inactive_image = SimpleUploadedFile("inactive.jpg", b"fake-image-content", content_type="image/jpeg")
        PlaygroundStyle.objects.create(
            name="Inactive Style",
            image=inactive_image,
            is_active=False,
            sort_order=2,
        )

    def _start_session(self):
        response = self.client.get(reverse("ai-playground-start"))
        self.assertEqual(response.status_code, 302)
        return PlaygroundSession.objects.latest("id")

    @staticmethod
    def _image_file(filename: str):
        return SimpleUploadedFile(filename, b"fake-image-content", content_type="image/jpeg")

    def test_styles_api_requires_session(self):
        response = self.client.get(reverse("ai-playground-styles"))
        self.assertEqual(response.status_code, 401)
        payload = response.json()
        self.assertFalse(payload["ok"])

    def test_styles_api_returns_active_styles_only(self):
        self._start_session()
        response = self.client.get(reverse("ai-playground-styles"))
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["styles"]), 1)
        self.assertEqual(payload["styles"][0]["id"], self.active_style.id)
        self.assertFalse(payload["has_selfie"])

    def test_upload_selfie_saves_it_on_session(self):
        session = self._start_session()
        response = self.client.post(
            reverse("ai-playground-selfie-upload"),
            {"image": self._image_file("selfie.jpg")},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertIn("selfie", payload)
        self.assertIn("url", payload["selfie"])

        session.refresh_from_db()
        self.assertTrue(session.has_selfie)
        self.assertIsNotNone(session.selfie_uploaded_at)

    def test_generate_requires_selfie_first(self):
        self._start_session()
        response = self.client.post(
            reverse("ai-playground-generate"),
            {"style_id": str(self.active_style.id)},
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertEqual(PlaygroundGeneration.objects.count(), 0)

    def test_generate_with_curated_style_creates_succeeded_generation(self):
        session = self._start_session()
        self.client.post(
            reverse("ai-playground-selfie-upload"),
            {"image": self._image_file("selfie.jpg")},
        )

        response = self.client.post(
            reverse("ai-playground-generate"),
            {"style_id": str(self.active_style.id)},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["generation"]["source"], "curated")
        self.assertTrue(payload["generation"]["result_url"])
        self.assertEqual(PlaygroundGeneration.objects.count(), 1)

        generation = PlaygroundGeneration.objects.first()
        self.assertEqual(generation.style_id, self.active_style.id)
        self.assertEqual(generation.status, "succeeded")
        self.assertEqual(generation.provider, "stub")
        self.assertTrue(bool(generation.result_image))

        session.refresh_from_db()
        self.assertEqual(session.generation_count, 1)

    def test_home_restores_latest_generation_after_refresh(self):
        self._start_session()
        self.client.post(
            reverse("ai-playground-selfie-upload"),
            {"image": self._image_file("selfie.jpg")},
        )
        self.client.post(
            reverse("ai-playground-generate"),
            {"style_id": str(self.active_style.id)},
        )
        generation = PlaygroundGeneration.objects.first()
        self.assertIsNotNone(generation)
        self.assertTrue(bool(generation.result_image))

        response = self.client.get(reverse("ai-playground-home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, generation.result_image.url)
        self.assertContains(response, f"#{generation.id}")

    def test_generate_with_custom_style_creates_succeeded_generation(self):
        session = self._start_session()
        self.client.post(
            reverse("ai-playground-selfie-upload"),
            {"image": self._image_file("selfie.jpg")},
        )

        response = self.client.post(
            reverse("ai-playground-generate"),
            {"custom_style_image": self._image_file("desired.jpg")},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["generation"]["source"], "custom")
        self.assertTrue(payload["generation"]["result_url"])
        self.assertEqual(PlaygroundGeneration.objects.count(), 1)

        generation = PlaygroundGeneration.objects.first()
        self.assertIsNone(generation.style)
        self.assertTrue(bool(generation.custom_style_image))
        self.assertEqual(generation.status, "succeeded")
        self.assertTrue(bool(generation.result_image))

        session.refresh_from_db()
        self.assertEqual(session.generation_count, 1)

    @override_settings(
        AI_PLAYGROUND_SESSION_GENERATION_LIMIT=1,
        AI_PLAYGROUND_MIN_GENERATE_INTERVAL_SECONDS=0,
    )
    def test_generate_enforces_session_quota(self):
        self._start_session()
        self.client.post(
            reverse("ai-playground-selfie-upload"),
            {"image": self._image_file("selfie.jpg")},
        )
        first = self.client.post(
            reverse("ai-playground-generate"),
            {"style_id": str(self.active_style.id)},
        )
        self.assertEqual(first.status_code, 200)

        second = self.client.post(
            reverse("ai-playground-generate"),
            {"custom_style_image": self._image_file("another.jpg")},
        )
        self.assertEqual(second.status_code, 429)
        payload = second.json()
        self.assertFalse(payload["ok"])
        self.assertIn("quota", payload["error"])

    @override_settings(
        AI_PLAYGROUND_MIN_GENERATE_INTERVAL_SECONDS=999,
    )
    def test_generate_enforces_min_interval(self):
        self._start_session()
        self.client.post(
            reverse("ai-playground-selfie-upload"),
            {"image": self._image_file("selfie.jpg")},
        )
        first = self.client.post(
            reverse("ai-playground-generate"),
            {"style_id": str(self.active_style.id)},
        )
        self.assertEqual(first.status_code, 200)

        second = self.client.post(
            reverse("ai-playground-generate"),
            {"custom_style_image": self._image_file("next.jpg")},
        )
        self.assertEqual(second.status_code, 429)
        self.assertIn("Retry-After", second.headers)
        payload = second.json()
        self.assertFalse(payload["ok"])
        self.assertIn("wait", payload["error"])

    @override_settings(
        AI_PLAYGROUND_ONE_STYLE_PER_SESSION=True,
        AI_PLAYGROUND_MIN_GENERATE_INTERVAL_SECONDS=0,
    )
    def test_generate_prevents_reusing_same_curated_style(self):
        self._start_session()
        self.client.post(
            reverse("ai-playground-selfie-upload"),
            {"image": self._image_file("selfie.jpg")},
        )
        first = self.client.post(
            reverse("ai-playground-generate"),
            {"style_id": str(self.active_style.id)},
        )
        self.assertEqual(first.status_code, 200)

        second = self.client.post(
            reverse("ai-playground-generate"),
            {"style_id": str(self.active_style.id)},
        )
        self.assertEqual(second.status_code, 409)
        payload = second.json()
        self.assertFalse(payload["ok"])
        self.assertIn("already used", payload["error"])

    @override_settings(
        AI_PLAYGROUND_GENERATE_MAX_PER_IP_PER_HOUR=1,
        AI_PLAYGROUND_MIN_GENERATE_INTERVAL_SECONDS=0,
    )
    def test_generate_is_rate_limited_per_ip(self):
        self._start_session()
        self.client.post(
            reverse("ai-playground-selfie-upload"),
            {"image": self._image_file("selfie.jpg")},
        )
        first = self.client.post(
            reverse("ai-playground-generate"),
            {"style_id": str(self.active_style.id)},
            REMOTE_ADDR="10.20.0.1",
        )
        self.assertEqual(first.status_code, 200)

        second = self.client.post(
            reverse("ai-playground-generate"),
            {"custom_style_image": self._image_file("next.jpg")},
            REMOTE_ADDR="10.20.0.1",
        )
        self.assertEqual(second.status_code, 429)
        payload = second.json()
        self.assertFalse(payload["ok"])
        self.assertIn("rate limit", payload["error"])

    @override_settings(
        AI_PLAYGROUND_PROVIDER="nanobanana",
        AI_PLAYGROUND_NANOBANANA_API_KEY="",
    )
    def test_generate_returns_failure_when_provider_not_configured(self):
        self._start_session()
        self.client.post(
            reverse("ai-playground-selfie-upload"),
            {"image": self._image_file("selfie.jpg")},
        )

        response = self.client.post(
            reverse("ai-playground-generate"),
            {"style_id": str(self.active_style.id)},
        )

        self.assertEqual(response.status_code, 502)
        payload = response.json()
        self.assertFalse(payload["ok"])
        generation = PlaygroundGeneration.objects.first()
        self.assertIsNotNone(generation)
        self.assertEqual(generation.status, "failed")


@override_settings(
    MEDIA_ROOT="/tmp/ai-playground-tests",
    AI_PLAYGROUND_PROVIDER="stub",
    AI_PLAYGROUND_DATA_RETENTION_HOURS=24,
)
class PlaygroundCleanupCommandTests(TestCase):
    def test_cleanup_command_removes_stale_records(self):
        stale_session = PlaygroundSession.objects.create(
            expires_at=timezone.now() - timedelta(hours=30),
        )
        fresh_session = PlaygroundSession.objects.create(
            expires_at=timezone.now() + timedelta(minutes=30),
        )

        stale_generation = PlaygroundGeneration.objects.create(
            session=stale_session,
            selfie_image=self._image_file("stale-selfie.jpg"),
            provider="stub",
            status="succeeded",
        )
        stale_generation.created_at = timezone.now() - timedelta(hours=30)
        stale_generation.save(update_fields=["created_at"])

        fresh_generation = PlaygroundGeneration.objects.create(
            session=fresh_session,
            selfie_image=self._image_file("fresh-selfie.jpg"),
            provider="stub",
            status="succeeded",
        )

        stale_event = PlaygroundRateLimitEvent.objects.create(
            action=PlaygroundRateLimitActionChoices.GENERATE,
            ip_address="10.30.0.1",
            session=stale_session,
        )
        stale_event.created_at = timezone.now() - timedelta(hours=30)
        stale_event.save(update_fields=["created_at"])

        call_command("cleanup_ai_playground", "--retention-hours", "24")

        self.assertFalse(PlaygroundSession.objects.filter(id=stale_session.id).exists())
        self.assertTrue(PlaygroundSession.objects.filter(id=fresh_session.id).exists())
        self.assertFalse(PlaygroundGeneration.objects.filter(id=stale_generation.id).exists())
        self.assertTrue(PlaygroundGeneration.objects.filter(id=fresh_generation.id).exists())
        self.assertFalse(PlaygroundRateLimitEvent.objects.filter(id=stale_event.id).exists())

    @staticmethod
    def _image_file(filename: str):
        return SimpleUploadedFile(filename, b"fake-image-content", content_type="image/jpeg")
