import base64
from contextlib import ExitStack
import io
import json
import logging
import mimetypes
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.conf import settings
from PIL import Image

from .prompts import (
    PROMPT_STYLE_FLASH,
    PROMPT_STYLE_PRO,
    build_hair_transformation_prompt,
)


class PlaygroundProviderError(RuntimeError):
    pass


@dataclass
class PlaygroundImageResult:
    image_bytes: bytes
    mime_type: str
    provider: str


@dataclass(frozen=True)
class GeminiUsageMetrics:
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None


@dataclass(frozen=True)
class GeminiTokenPricing:
    input_cost_per_1m_tokens: float
    output_cost_per_1m_tokens: float


NANOBANANA_USAGE_LOGGER = logging.getLogger("ai_playground.nanobanana.usage")
NANOBANANA_MODEL_PRICING: dict[str, GeminiTokenPricing] = {
    "gemini-2.5-flash-image": GeminiTokenPricing(
        input_cost_per_1m_tokens=0.30,
        output_cost_per_1m_tokens=30.00,
    ),
    "gemini-3-pro-image-preview": GeminiTokenPricing(
        input_cost_per_1m_tokens=2.00,
        output_cost_per_1m_tokens=120.00,
    ),
}
NANOBANANA_IMAGE_SIZE_OPTIONS = {"1K", "2K", "4K"}
NANOBANANA_PRO_IMAGE_MODEL_PREFIX = "gemini-3-pro-image-preview"
NANOBANANA_PROMPT_SET_OPTIONS = {1, 2, 3, 4, 5}
NANOBANANA_DEFAULT_PROMPT_SET = 1


def configured_provider_name() -> str:
    return str(getattr(settings, "AI_PLAYGROUND_PROVIDER", "stub")).strip().lower() or "stub"


def generate_hair_preview(
    *,
    selfie_path: str,
    reference_path: str,
    beard_reference_path: str | None = None,
    hair_color_name: str = "",
    beard_color_name: str = "",
    apply_beard_edit: bool = False,
) -> PlaygroundImageResult:
    provider_name = configured_provider_name()
    provider = _provider_factory(provider_name)
    return provider.generate(
        selfie_path=selfie_path,
        reference_path=reference_path,
        beard_reference_path=beard_reference_path,
        hair_color_name=hair_color_name,
        beard_color_name=beard_color_name,
        apply_beard_edit=apply_beard_edit,
    )


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


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _normalize_model_id(model_name: str) -> str:
    normalized = str(model_name or "").strip().lower()
    if "/" in normalized:
        normalized = normalized.split("/")[-1]
    return normalized


def _nanobanana_model_pricing(model_name: str) -> GeminiTokenPricing | None:
    normalized_model = _normalize_model_id(model_name)
    for model_prefix, pricing in NANOBANANA_MODEL_PRICING.items():
        if normalized_model == model_prefix or normalized_model.startswith(f"{model_prefix}-"):
            return pricing
    return None


def _is_nanobanana_pro_image_model(model_name: str) -> bool:
    normalized_model = _normalize_model_id(model_name)
    return normalized_model == NANOBANANA_PRO_IMAGE_MODEL_PREFIX or normalized_model.startswith(
        f"{NANOBANANA_PRO_IMAGE_MODEL_PREFIX}-"
    )


def _extract_gemini_usage_metrics(payload: dict[str, Any]) -> GeminiUsageMetrics:
    usage = payload.get("usageMetadata")
    if usage is None:
        usage = payload.get("usage_metadata")
    if not isinstance(usage, dict):
        return GeminiUsageMetrics(prompt_tokens=None, completion_tokens=None, total_tokens=None)

    prompt_tokens = _safe_int(
        _first_present(
            usage.get("promptTokenCount"),
            usage.get("prompt_token_count"),
        )
    )
    completion_tokens = _safe_int(
        _first_present(
            usage.get("candidatesTokenCount"),
            usage.get("candidates_token_count"),
            usage.get("outputTokenCount"),
            usage.get("output_token_count"),
        )
    )
    total_tokens = _safe_int(
        _first_present(
            usage.get("totalTokenCount"),
            usage.get("total_token_count"),
        )
    )
    if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
        total_tokens = prompt_tokens + completion_tokens
    return GeminiUsageMetrics(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )


def _estimate_nanobanana_cost_usd(
    *,
    usage: GeminiUsageMetrics,
    input_cost_per_1m_tokens: float,
    output_cost_per_1m_tokens: float,
) -> float | None:
    input_rate = max(0.0, float(input_cost_per_1m_tokens))
    output_rate = max(0.0, float(output_cost_per_1m_tokens))
    has_input_rate = input_rate > 0
    has_output_rate = output_rate > 0

    if usage.prompt_tokens is not None and usage.completion_tokens is not None and (has_input_rate or has_output_rate):
        return ((usage.prompt_tokens * input_rate) + (usage.completion_tokens * output_rate)) / 1_000_000

    if usage.total_tokens is not None:
        if has_input_rate and has_output_rate:
            average_rate = (input_rate + output_rate) / 2
            return (usage.total_tokens * average_rate) / 1_000_000
        if has_input_rate:
            return (usage.total_tokens * input_rate) / 1_000_000
        if has_output_rate:
            return (usage.total_tokens * output_rate) / 1_000_000

    return None


def _log_nanobanana_usage(
    *,
    model: str,
    prompt_style: str,
    prompt_set: int,
    usage: GeminiUsageMetrics,
    estimated_cost_usd: float | None,
) -> None:
    prompt_value = "unknown" if usage.prompt_tokens is None else str(usage.prompt_tokens)
    completion_value = "unknown" if usage.completion_tokens is None else str(usage.completion_tokens)
    total_value = "unknown" if usage.total_tokens is None else str(usage.total_tokens)
    cost_value = "unknown" if estimated_cost_usd is None else f"{estimated_cost_usd:.8f}"
    NANOBANANA_USAGE_LOGGER.info(
        (
            "nanobanana_usage model=%s prompt_style=%s prompt_set=%s "
            "prompt_tokens=%s completion_tokens=%s total_tokens=%s estimated_cost_usd=%s"
        ),
        model,
        prompt_style,
        str(prompt_set),
        prompt_value,
        completion_value,
        total_value,
        cost_value,
    )


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


def _build_composite_reference(selfie_path: str, reference_paths: list[str]) -> bytes:
    panel_paths = [selfie_path, *reference_paths]
    with ExitStack() as stack:
        raw_images = [stack.enter_context(Image.open(path)) for path in panel_paths]
        converted = [image.convert("RGB") for image in raw_images]
        heights = [img.height for img in converted]
        target_height = min(max(heights), 1024)
        resized_images = []
        for image in converted:
            width = max(1, int(image.width * target_height / max(image.height, 1)))
            resized_images.append(image.resize((width, target_height), Image.Resampling.LANCZOS))

        total_width = sum(image.width for image in resized_images)
        composed = Image.new("RGB", (total_width, target_height), color=(245, 245, 245))
        x_offset = 0
        for image in resized_images:
            composed.paste(image, (x_offset, 0))
            x_offset += image.width

        buffer = io.BytesIO()
        composed.save(buffer, format="JPEG", quality=93)
        return buffer.getvalue()


class StubProvider:
    provider = "stub"

    def generate(
        self,
        *,
        selfie_path: str,
        reference_path: str,
        beard_reference_path: str | None = None,
        hair_color_name: str = "",
        beard_color_name: str = "",
        apply_beard_edit: bool = False,
    ) -> PlaygroundImageResult:
        _ = beard_reference_path, hair_color_name, beard_color_name, apply_beard_edit
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
            getattr(settings, "AI_PLAYGROUND_NANOBANANA_MODEL", "gemini-2.5-flash-image")
        ).strip()
        self.timeout_seconds = int(getattr(settings, "AI_PLAYGROUND_PROVIDER_TIMEOUT_SECONDS", 120))
        self.image_size_override = str(
            getattr(settings, "AI_PLAYGROUND_NANOBANANA_IMAGE_SIZE", "")
        ).strip().upper()
        self.default_prompt_set = str(getattr(settings, "AI_PLAYGROUND_NANOBANANA_PROMPT_SET", "1")).strip()
        self.flash_prompt_set = str(getattr(settings, "AI_PLAYGROUND_NANOBANANA_FLASH_PROMPT_SET", "")).strip()
        self.pro_prompt_set = str(getattr(settings, "AI_PLAYGROUND_NANOBANANA_PRO_PROMPT_SET", "")).strip()
        model_pricing = _nanobanana_model_pricing(self.model)
        if model_pricing:
            self.input_cost_per_1m_tokens = model_pricing.input_cost_per_1m_tokens
            self.output_cost_per_1m_tokens = model_pricing.output_cost_per_1m_tokens
        else:
            self.input_cost_per_1m_tokens = _safe_float(
                getattr(settings, "AI_PLAYGROUND_NANOBANANA_INPUT_COST_PER_1M_TOKENS", 0)
            )
            self.output_cost_per_1m_tokens = _safe_float(
                getattr(settings, "AI_PLAYGROUND_NANOBANANA_OUTPUT_COST_PER_1M_TOKENS", 0)
            )
        endpoint_override = str(getattr(settings, "AI_PLAYGROUND_NANOBANANA_ENDPOINT", "")).strip()
        if endpoint_override:
            self.endpoint = endpoint_override
        else:
            self.endpoint = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{quote(self.model, safe='')}:generateContent"
            )

    def _resolved_image_size(self) -> str | None:
        if not _is_nanobanana_pro_image_model(self.model):
            return None
        if self.image_size_override in NANOBANANA_IMAGE_SIZE_OPTIONS:
            return self.image_size_override
        return "1K"

    def _resolved_prompt_style(self) -> str:
        if _is_nanobanana_pro_image_model(self.model):
            return PROMPT_STYLE_PRO
        return PROMPT_STYLE_FLASH

    def _resolved_prompt_set(self) -> int:
        if _is_nanobanana_pro_image_model(self.model):
            raw_prompt_set = self.pro_prompt_set or self.default_prompt_set
        else:
            raw_prompt_set = self.flash_prompt_set or self.default_prompt_set
        parsed_prompt_set = _safe_int(raw_prompt_set)
        if parsed_prompt_set in NANOBANANA_PROMPT_SET_OPTIONS:
            return int(parsed_prompt_set)
        return NANOBANANA_DEFAULT_PROMPT_SET

    def generate(
        self,
        *,
        selfie_path: str,
        reference_path: str,
        beard_reference_path: str | None = None,
        hair_color_name: str = "",
        beard_color_name: str = "",
        apply_beard_edit: bool = False,
    ) -> PlaygroundImageResult:
        if not self.api_key:
            raise PlaygroundProviderError("Nanobanana API key is missing.")

        resolved_prompt_style = self._resolved_prompt_style()
        resolved_prompt_set = self._resolved_prompt_set()

        selfie_mime, selfie_b64 = _image_file_as_base64(selfie_path)
        reference_mime, reference_b64 = _image_file_as_base64(reference_path)
        beard_mime = ""
        beard_b64 = ""
        if beard_reference_path:
            beard_mime, beard_b64 = _image_file_as_base64(beard_reference_path)

        content_parts = [
            {"text": "Image 1 (identity anchor selfie):"},
            {"inlineData": {"mimeType": selfie_mime, "data": selfie_b64}},
            {"text": "Image 2 (target hairstyle reference):"},
            {"inlineData": {"mimeType": reference_mime, "data": reference_b64}},
        ]
        if beard_reference_path:
            content_parts.extend(
                [
                    {"text": "Image 3 (target beard reference):"},
                    {"inlineData": {"mimeType": beard_mime, "data": beard_b64}},
                ]
            )
        content_parts.append(
            {
                "text": build_hair_transformation_prompt(
                    use_composite_input=False,
                    include_beard_reference=bool(beard_reference_path),
                    hair_color_name=hair_color_name,
                    beard_color_name=beard_color_name,
                    apply_beard_edit=apply_beard_edit,
                    prompt_style=resolved_prompt_style,
                    prompt_set=resolved_prompt_set,
                )
            }
        )

        generation_config: dict[str, Any] = {"responseModalities": ["IMAGE"]}
        image_size = self._resolved_image_size()
        if image_size:
            generation_config["imageConfig"] = {"imageSize": image_size}

        payload = {
            "contents": [
                {
                    "parts": content_parts,
                }
            ],
            "generationConfig": generation_config,
        }

        response_payload = _post_json(
            self.endpoint,
            payload,
            headers={"x-goog-api-key": self.api_key},
            timeout_seconds=self.timeout_seconds,
        )
        usage_metrics = _extract_gemini_usage_metrics(response_payload)
        estimated_cost_usd = _estimate_nanobanana_cost_usd(
            usage=usage_metrics,
            input_cost_per_1m_tokens=self.input_cost_per_1m_tokens,
            output_cost_per_1m_tokens=self.output_cost_per_1m_tokens,
        )
        _log_nanobanana_usage(
            model=self.model,
            prompt_style=resolved_prompt_style,
            prompt_set=resolved_prompt_set,
            usage=usage_metrics,
            estimated_cost_usd=estimated_cost_usd,
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

    def generate(
        self,
        *,
        selfie_path: str,
        reference_path: str,
        beard_reference_path: str | None = None,
        hair_color_name: str = "",
        beard_color_name: str = "",
        apply_beard_edit: bool = False,
    ) -> PlaygroundImageResult:
        if not self.api_key:
            raise PlaygroundProviderError("Grok API key is missing.")

        reference_paths = [reference_path]
        if beard_reference_path:
            reference_paths.append(beard_reference_path)
        composite_bytes = _build_composite_reference(selfie_path, reference_paths)
        composite_b64 = base64.b64encode(composite_bytes).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{composite_b64}"

        payload = {
            "model": self.model,
            "prompt": build_hair_transformation_prompt(
                use_composite_input=True,
                include_beard_reference=bool(beard_reference_path),
                hair_color_name=hair_color_name,
                beard_color_name=beard_color_name,
                apply_beard_edit=apply_beard_edit,
                prompt_style=PROMPT_STYLE_PRO,
            ),
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
