import base64
import io
import json
import mimetypes
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.conf import settings
from PIL import Image

from .prompts import build_hair_transformation_prompt


class PlaygroundProviderError(RuntimeError):
    pass


@dataclass
class PlaygroundImageResult:
    image_bytes: bytes
    mime_type: str
    provider: str


def configured_provider_name() -> str:
    return str(getattr(settings, "AI_PLAYGROUND_PROVIDER", "stub")).strip().lower() or "stub"


def generate_hair_preview(
    *,
    selfie_path: str,
    reference_path: str,
) -> PlaygroundImageResult:
    provider_name = configured_provider_name()
    provider = _provider_factory(provider_name)
    return provider.generate(selfie_path=selfie_path, reference_path=reference_path)


def _provider_factory(provider_name: str):
    if provider_name == "nanobanana":
        return NanobananaProvider()
    if provider_name == "grok":
        return GrokImagesProvider()
    if provider_name == "stub":
        return StubProvider()
    raise PlaygroundProviderError(
        f"Unsupported provider '{provider_name}'. "
        "Set AI_PLAYGROUND_PROVIDER to one of: nanobanana, grok, stub."
    )


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout_seconds: int) -> dict[str, Any]:
    request_data = json.dumps(payload).encode("utf-8")
    request_headers = {"Content-Type": "application/json", **headers}
    request = Request(url=url, data=request_data, headers=request_headers, method="POST")
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
            if not body:
                return {}
            return json.loads(body)
    except HTTPError as error:
        error_body = error.read().decode("utf-8", errors="ignore")
        message = f"Provider HTTP {error.code}"
        if error_body:
            message = f"{message}: {error_body[:500]}"
        raise PlaygroundProviderError(message) from error
    except URLError as error:
        raise PlaygroundProviderError(f"Provider connection failed: {error.reason}") from error
    except json.JSONDecodeError as error:
        raise PlaygroundProviderError("Provider returned invalid JSON.") from error


def _download_binary(url: str, timeout_seconds: int) -> tuple[bytes, str]:
    request = Request(url=url, method="GET")
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            image_bytes = response.read()
            content_type = response.headers.get("Content-Type", "")
            mime_type = content_type.split(";")[0].strip() or "image/png"
            return image_bytes, mime_type
    except HTTPError as error:
        raise PlaygroundProviderError(f"Could not download generated image. HTTP {error.code}.") from error
    except URLError as error:
        raise PlaygroundProviderError(f"Could not download generated image: {error.reason}.") from error


def _guess_mime_type(file_path: str) -> str:
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type or "image/jpeg"


def _image_file_as_base64(file_path: str) -> tuple[str, str]:
    with open(file_path, "rb") as file_obj:
        raw_bytes = file_obj.read()
    return _guess_mime_type(file_path), base64.b64encode(raw_bytes).decode("utf-8")


def _decode_base64_payload(raw_value: str) -> bytes:
    try:
        return base64.b64decode(raw_value)
    except (ValueError, TypeError) as error:
        raise PlaygroundProviderError("Provider returned invalid base64 image payload.") from error


def _extract_gemini_image(payload: dict[str, Any]) -> tuple[bytes, str]:
    candidates = payload.get("candidates", [])
    for candidate in candidates:
        content = candidate.get("content") or {}
        parts = content.get("parts") or []
        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                return _decode_base64_payload(inline["data"]), mime
    raise PlaygroundProviderError("Nanobanana provider returned no image output.")


def _extract_grok_image(payload: dict[str, Any], timeout_seconds: int) -> tuple[bytes, str]:
    data_list = payload.get("data")
    if isinstance(data_list, list) and data_list:
        first = data_list[0] or {}
        if first.get("b64_json"):
            return _decode_base64_payload(first["b64_json"]), "image/png"
        if first.get("url"):
            return _download_binary(first["url"], timeout_seconds)

    if payload.get("b64_json"):
        return _decode_base64_payload(payload["b64_json"]), "image/png"
    if payload.get("url"):
        return _download_binary(payload["url"], timeout_seconds)
    if payload.get("image"):
        return _decode_base64_payload(payload["image"]), "image/png"

    raise PlaygroundProviderError("Grok provider returned no image output.")


def _build_composite_reference(selfie_path: str, reference_path: str) -> bytes:
    with Image.open(selfie_path) as selfie_raw, Image.open(reference_path) as reference_raw:
        selfie = selfie_raw.convert("RGB")
        reference = reference_raw.convert("RGB")

        target_height = min(max(selfie.height, reference.height), 1024)
        selfie_width = max(1, int(selfie.width * target_height / max(selfie.height, 1)))
        ref_width = max(1, int(reference.width * target_height / max(reference.height, 1)))

        selfie_resized = selfie.resize((selfie_width, target_height), Image.Resampling.LANCZOS)
        reference_resized = reference.resize((ref_width, target_height), Image.Resampling.LANCZOS)

        composed = Image.new("RGB", (selfie_width + ref_width, target_height), color=(245, 245, 245))
        composed.paste(selfie_resized, (0, 0))
        composed.paste(reference_resized, (selfie_width, 0))

        buffer = io.BytesIO()
        composed.save(buffer, format="JPEG", quality=93)
        return buffer.getvalue()


class StubProvider:
    provider = "stub"

    def generate(self, *, selfie_path: str, reference_path: str) -> PlaygroundImageResult:
        _ = reference_path
        with open(selfie_path, "rb") as file_obj:
            image_bytes = file_obj.read()
        return PlaygroundImageResult(
            image_bytes=image_bytes,
            mime_type=_guess_mime_type(selfie_path),
            provider=self.provider,
        )


class NanobananaProvider:
    provider = "nanobanana"

    def __init__(self):
        self.api_key = str(getattr(settings, "AI_PLAYGROUND_NANOBANANA_API_KEY", "")).strip()
        self.model = str(
            getattr(settings, "AI_PLAYGROUND_NANOBANANA_MODEL", "gemini-2.5-flash-image-preview")
        ).strip()
        self.timeout_seconds = int(getattr(settings, "AI_PLAYGROUND_PROVIDER_TIMEOUT_SECONDS", 120))
        endpoint_override = str(getattr(settings, "AI_PLAYGROUND_NANOBANANA_ENDPOINT", "")).strip()
        if endpoint_override:
            self.endpoint = endpoint_override
        else:
            self.endpoint = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{quote(self.model, safe='')}:generateContent"
            )

    def generate(self, *, selfie_path: str, reference_path: str) -> PlaygroundImageResult:
        if not self.api_key:
            raise PlaygroundProviderError("Nanobanana API key is missing.")

        selfie_mime, selfie_b64 = _image_file_as_base64(selfie_path)
        reference_mime, reference_b64 = _image_file_as_base64(reference_path)

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": "Image 1 (identity anchor selfie):"},
                        {"inlineData": {"mimeType": selfie_mime, "data": selfie_b64}},
                        {"text": "Image 2 (target haircut reference):"},
                        {"inlineData": {"mimeType": reference_mime, "data": reference_b64}},
                        {
                            "text": build_hair_transformation_prompt(
                                use_composite_input=False,
                            )
                        },
                    ]
                }
            ],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        }

        response_payload = _post_json(
            self.endpoint,
            payload,
            headers={"x-goog-api-key": self.api_key},
            timeout_seconds=self.timeout_seconds,
        )
        image_bytes, mime_type = _extract_gemini_image(response_payload)
        return PlaygroundImageResult(image_bytes=image_bytes, mime_type=mime_type, provider=self.provider)


class GrokImagesProvider:
    provider = "grok"

    def __init__(self):
        self.api_key = str(getattr(settings, "AI_PLAYGROUND_GROK_API_KEY", "")).strip()
        self.model = str(getattr(settings, "AI_PLAYGROUND_GROK_MODEL", "grok-2-image")).strip()
        self.endpoint = str(
            getattr(settings, "AI_PLAYGROUND_GROK_IMAGES_ENDPOINT", "https://api.x.ai/v1/images/edits")
        ).strip()
        self.timeout_seconds = int(getattr(settings, "AI_PLAYGROUND_PROVIDER_TIMEOUT_SECONDS", 120))
        self.output_format = str(getattr(settings, "AI_PLAYGROUND_GROK_IMAGE_FORMAT", "base64")).strip()

    def generate(self, *, selfie_path: str, reference_path: str) -> PlaygroundImageResult:
        if not self.api_key:
            raise PlaygroundProviderError("Grok API key is missing.")

        composite_bytes = _build_composite_reference(selfie_path, reference_path)
        composite_b64 = base64.b64encode(composite_bytes).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{composite_b64}"

        payload = {
            "model": self.model,
            "prompt": build_hair_transformation_prompt(use_composite_input=True),
            "image_url": data_url,
            "image_format": self.output_format,
        }
        response_payload = _post_json(
            self.endpoint,
            payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout_seconds=self.timeout_seconds,
        )
        image_bytes, mime_type = _extract_grok_image(response_payload, self.timeout_seconds)
        return PlaygroundImageResult(image_bytes=image_bytes, mime_type=mime_type, provider=self.provider)


def extension_from_mime(mime_type: str) -> str:
    guessed = mimetypes.guess_extension(mime_type or "")
    if guessed:
        return guessed.lstrip(".")
    return "png"
