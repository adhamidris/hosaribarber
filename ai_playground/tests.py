import base64
from datetime import timedelta
from unittest.mock import patch

from django.core import signing
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    PlaygroundBeardStyle,
    PlaygroundColorOption,
    PlaygroundColorScopeChoices,
    PlaygroundGeneration,
    PlaygroundRateLimitActionChoices,
    PlaygroundRateLimitEvent,
    PlaygroundSession,
    PlaygroundStyle,
)
from .services import (
    GeminiUsageMetrics,
    NanobananaProvider,
    _estimate_nanobanana_cost_usd,
    _extract_gemini_usage_metrics,
    _nanobanana_model_pricing,
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
        beard_style_image = SimpleUploadedFile("beard.jpg", b"fake-image-content", content_type="image/jpeg")
        self.active_beard_style = PlaygroundBeardStyle.objects.create(
            name="Short Boxed",
            image=beard_style_image,
            is_active=True,
            sort_order=1,
        )
        self.hair_color = PlaygroundColorOption.objects.create(
            name="Dark Brown",
            hex_code="#3E2D22",
            scope=PlaygroundColorScopeChoices.HAIR,
            is_active=True,
            sort_order=1,
        )
        self.beard_color = PlaygroundColorOption.objects.create(
            name="Soft Black",
            hex_code="#1F1F1F",
            scope=PlaygroundColorScopeChoices.BEARD,
            is_active=True,
            sort_order=1,
        )

    def _start_session(self):
        response = self.client.get(reverse("ai-playground-start"))
        self.assertEqual(response.status_code, 302)
        return PlaygroundSession.objects.latest("id")

    @staticmethod
    def _image_file(filename: str):
        return SimpleUploadedFile(filename, b"fake-image-content", content_type="image/jpeg")

    @staticmethod
    def _selection_payload(
        *,
        hair_color_option_id: str = "none",
        beard_style_id: str = "none",
        beard_color_option_id: str = "none",
    ) -> dict[str, str]:
        return {
            "hair_color_option_id": hair_color_option_id,
            "beard_style_id": beard_style_id,
            "beard_color_option_id": beard_color_option_id,
        }

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
        self.assertEqual(len(payload["beard_styles"]), 1)
        self.assertEqual(payload["beard_styles"][0]["id"], self.active_beard_style.id)
        hair_color_ids = {item["id"] for item in payload["hair_colors"]}
        beard_color_ids = {item["id"] for item in payload["beard_colors"]}
        self.assertIn(self.hair_color.id, hair_color_ids)
        self.assertIn(self.beard_color.id, beard_color_ids)
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

    def test_home_restores_saved_selfie_after_refresh(self):
        session = self._start_session()
        upload_response = self.client.post(
            reverse("ai-playground-selfie-upload"),
            {"image": self._image_file("selfie.jpg")},
        )
        self.assertEqual(upload_response.status_code, 200)

        session.refresh_from_db()
        self.assertTrue(session.has_selfie)
        self.assertTrue(bool(session.selfie_image))

        home_response = self.client.get(reverse("ai-playground-home"))
        self.assertEqual(home_response.status_code, 200)
        self.assertContains(home_response, 'data-has-selfie="true"')
        self.assertContains(home_response, session.selfie_image.url)

    def test_generate_requires_selfie_first(self):
        self._start_session()
        response = self.client.post(
            reverse("ai-playground-generate"),
            {
                "style_id": str(self.active_style.id),
                **self._selection_payload(),
            },
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertEqual(PlaygroundGeneration.objects.count(), 0)

    def test_generate_requires_style_panel_choices(self):
        self._start_session()
        self.client.post(
            reverse("ai-playground-selfie-upload"),
            {"image": self._image_file("selfie.jpg")},
        )
        response = self.client.post(
            reverse("ai-playground-generate"),
            {"style_id": str(self.active_style.id)},
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertIn("hair color", payload["error"].lower())

    def test_generate_with_curated_style_creates_succeeded_generation(self):
        session = self._start_session()
        self.client.post(
            reverse("ai-playground-selfie-upload"),
            {"image": self._image_file("selfie.jpg")},
        )

        response = self.client.post(
            reverse("ai-playground-generate"),
            {
                "style_id": str(self.active_style.id),
                **self._selection_payload(),
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["generation"]["source"], "curated")
        self.assertTrue(payload["generation"]["result_url"])
        self.assertNotIn("token_usage", payload["generation"])
        self.assertNotIn("estimated_cost_usd", payload["generation"])
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
            {
                "style_id": str(self.active_style.id),
                **self._selection_payload(),
            },
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
            {
                "custom_style_image": self._image_file("desired.jpg"),
                **self._selection_payload(),
            },
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
            {
                "style_id": str(self.active_style.id),
                **self._selection_payload(),
            },
        )
        self.assertEqual(first.status_code, 200)

        second = self.client.post(
            reverse("ai-playground-generate"),
            {
                "custom_style_image": self._image_file("another.jpg"),
                **self._selection_payload(),
            },
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
            {
                "style_id": str(self.active_style.id),
                **self._selection_payload(),
            },
        )
        self.assertEqual(first.status_code, 200)

        second = self.client.post(
            reverse("ai-playground-generate"),
            {
                "custom_style_image": self._image_file("next.jpg"),
                **self._selection_payload(),
            },
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
    def test_generate_reuses_cached_result_for_same_curated_style(self):
        session = self._start_session()
        self.client.post(
            reverse("ai-playground-selfie-upload"),
            {"image": self._image_file("selfie.jpg")},
        )
        first = self.client.post(
            reverse("ai-playground-generate"),
            {
                "style_id": str(self.active_style.id),
                **self._selection_payload(),
            },
        )
        self.assertEqual(first.status_code, 200)
        first_payload = first.json()

        second = self.client.post(
            reverse("ai-playground-generate"),
            {
                "style_id": str(self.active_style.id),
                **self._selection_payload(),
            },
        )
        self.assertEqual(second.status_code, 200)
        payload = second.json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["reused"])
        self.assertEqual(payload["generation"]["id"], first_payload["generation"]["id"])
        self.assertEqual(payload["generation"]["session_generation_count"], 1)
        self.assertEqual(PlaygroundGeneration.objects.count(), 1)
        session.refresh_from_db()
        self.assertEqual(session.generation_count, 1)

    @override_settings(
        AI_PLAYGROUND_MIN_GENERATE_INTERVAL_SECONDS=0,
    )
    def test_generate_reuses_cached_result_for_same_custom_style(self):
        session = self._start_session()
        self.client.post(
            reverse("ai-playground-selfie-upload"),
            {"image": self._image_file("selfie.jpg")},
        )
        first = self.client.post(
            reverse("ai-playground-generate"),
            {
                "custom_style_image": self._image_file("custom.jpg"),
                **self._selection_payload(),
            },
        )
        self.assertEqual(first.status_code, 200)
        first_payload = first.json()

        second = self.client.post(
            reverse("ai-playground-generate"),
            {
                "custom_style_image": self._image_file("custom.jpg"),
                **self._selection_payload(),
            },
        )
        self.assertEqual(second.status_code, 200)
        payload = second.json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["reused"])
        self.assertEqual(payload["generation"]["id"], first_payload["generation"]["id"])
        self.assertEqual(payload["generation"]["session_generation_count"], 1)
        self.assertEqual(PlaygroundGeneration.objects.count(), 1)
        session.refresh_from_db()
        self.assertEqual(session.generation_count, 1)

    @override_settings(
        AI_PLAYGROUND_ONE_STYLE_PER_SESSION=True,
        AI_PLAYGROUND_MIN_GENERATE_INTERVAL_SECONDS=0,
    )
    def test_generate_does_not_reuse_curated_style_after_selfie_changes(self):
        session = self._start_session()
        self.client.post(
            reverse("ai-playground-selfie-upload"),
            {"image": self._image_file("selfie-a.jpg")},
        )
        first = self.client.post(
            reverse("ai-playground-generate"),
            {
                "style_id": str(self.active_style.id),
                **self._selection_payload(),
            },
        )
        self.assertEqual(first.status_code, 200)
        first_payload = first.json()

        upload_second_selfie = self.client.post(
            reverse("ai-playground-selfie-upload"),
            {"image": self._image_file("selfie-b.jpg")},
        )
        self.assertEqual(upload_second_selfie.status_code, 200)

        second = self.client.post(
            reverse("ai-playground-generate"),
            {
                "style_id": str(self.active_style.id),
                **self._selection_payload(),
            },
        )
        self.assertEqual(second.status_code, 200)
        second_payload = second.json()
        self.assertNotEqual(second_payload["generation"]["id"], first_payload["generation"]["id"])
        self.assertFalse(second_payload.get("reused", False))
        self.assertEqual(PlaygroundGeneration.objects.count(), 2)
        session.refresh_from_db()
        self.assertEqual(session.generation_count, 2)

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
            {
                "style_id": str(self.active_style.id),
                **self._selection_payload(),
            },
            REMOTE_ADDR="10.20.0.1",
        )
        self.assertEqual(first.status_code, 200)

        second = self.client.post(
            reverse("ai-playground-generate"),
            {
                "custom_style_image": self._image_file("next.jpg"),
                **self._selection_payload(),
            },
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
            {
                "style_id": str(self.active_style.id),
                **self._selection_payload(),
            },
        )

        self.assertEqual(response.status_code, 502)
        payload = response.json()
        self.assertFalse(payload["ok"])
        generation = PlaygroundGeneration.objects.first()
        self.assertIsNotNone(generation)
        self.assertEqual(generation.status, "failed")


class PlaygroundNanobananaUsageTests(TestCase):
    def test_extract_gemini_usage_metrics_from_usage_metadata(self):
        payload = {
            "usageMetadata": {
                "promptTokenCount": 123,
                "candidatesTokenCount": 45,
            }
        }

        usage = _extract_gemini_usage_metrics(payload)

        self.assertEqual(usage.prompt_tokens, 123)
        self.assertEqual(usage.completion_tokens, 45)
        self.assertEqual(usage.total_tokens, 168)

    def test_estimate_cost_uses_prompt_and_completion_rates(self):
        usage = GeminiUsageMetrics(prompt_tokens=1000, completion_tokens=500, total_tokens=1500)

        estimate = _estimate_nanobanana_cost_usd(
            usage=usage,
            input_cost_per_1m_tokens=0.30,
            output_cost_per_1m_tokens=1.20,
        )

        self.assertAlmostEqual(estimate, 0.0009)

    def test_model_pricing_for_flash_image(self):
        pricing = _nanobanana_model_pricing("gemini-2.5-flash-image")
        self.assertIsNotNone(pricing)
        self.assertEqual(pricing.input_cost_per_1m_tokens, 0.30)
        self.assertEqual(pricing.output_cost_per_1m_tokens, 30.00)

    def test_model_pricing_for_pro_image(self):
        pricing = _nanobanana_model_pricing("gemini-3-pro-image-preview")
        self.assertIsNotNone(pricing)
        self.assertEqual(pricing.input_cost_per_1m_tokens, 2.00)
        self.assertEqual(pricing.output_cost_per_1m_tokens, 120.00)

    @override_settings(
        AI_PLAYGROUND_NANOBANANA_API_KEY="test-api-key",
        AI_PLAYGROUND_NANOBANANA_MODEL="gemini-2.5-flash-image",
        AI_PLAYGROUND_NANOBANANA_INPUT_COST_PER_1M_TOKENS="0.10",
        AI_PLAYGROUND_NANOBANANA_OUTPUT_COST_PER_1M_TOKENS="0.40",
    )
    def test_nanobanana_provider_logs_usage_and_estimated_cost(self):
        response_payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "inlineData": {
                                    "mimeType": "image/png",
                                    "data": base64.b64encode(b"fake-image").decode("utf-8"),
                                }
                            }
                        ]
                    }
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 1200,
                "candidatesTokenCount": 300,
                "totalTokenCount": 1500,
            },
        }

        with (
            patch(
                "ai_playground.services._image_file_as_base64",
                side_effect=[("image/jpeg", "selfie-data"), ("image/jpeg", "style-data")],
            ),
            patch("ai_playground.services._post_json", return_value=response_payload),
            patch("ai_playground.services.NANOBANANA_USAGE_LOGGER.info") as usage_log_info,
        ):
            result = NanobananaProvider().generate(
                selfie_path="/tmp/selfie.jpg",
                reference_path="/tmp/reference.jpg",
            )

        self.assertEqual(result.provider, "nanobanana")
        usage_log_info.assert_called_once()
        self.assertEqual(
            usage_log_info.call_args[0],
            (
                "nanobanana_usage model=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s estimated_cost_usd=%s",
                "gemini-2.5-flash-image",
                "1200",
                "300",
                "1500",
                "0.00936000",
            ),
        )


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
