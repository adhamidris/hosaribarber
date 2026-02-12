import base64
from contextlib import ExitStack
import io
import json
import logging
import mimetypes
import os
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.conf import settings
from PIL import Image

from .prompts import (
    PROMPT_MODE_CATALOG,
    PROMPT_MODE_EXPERT,
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
HAIRFASTGAN_ALIGN_OPTIONS = {"Face", "Shape", "Color"}
HAIRFASTGAN_DEFAULT_ALIGN = ["Face", "Shape", "Color"]
HAIRFASTGAN_BLEND_OPTIONS = {"Article", "Alternative_v1", "Alternative_v2"}
HAIRCLIP_SUPPORTED_HAIRSTYLES = {
    "afro hairstyle",
    "bob cut hairstyle",
    "bowl cut hairstyle",
    "braid hairstyle",
    "caesar cut hairstyle",
    "chignon hairstyle",
    "cornrows hairstyle",
    "crew cut hairstyle",
    "crown braid hairstyle",
    "curtained hair hairstyle",
    "dido flip hairstyle",
    "dreadlocks hairstyle",
    "extensions hairstyle",
    "fade hairstyle",
    "fauxhawk hairstyle",
    "finger waves hairstyle",
    "french braid hairstyle",
    "frosted tips hairstyle",
    "full crown hairstyle",
    "harvard clip hairstyle",
    "hi-top fade hairstyle",
    "high and tight hairstyle",
    "hime cut hairstyle",
    "jewfro hairstyle",
    "jheri curl hairstyle",
    "liberty spikes hairstyle",
    "marcel waves hairstyle",
    "mohawk hairstyle",
    "pageboy hairstyle",
    "perm hairstyle",
    "pixie cut hairstyle",
    "psychobilly wedge hairstyle",
    "quiff hairstyle",
    "regular taper cut hairstyle",
    "ringlets hairstyle",
    "shingle bob hairstyle",
    "short hair hairstyle",
    "slicked-back hairstyle",
    "spiky hair hairstyle",
    "surfer hair hairstyle",
    "taper cut hairstyle",
    "the rachel hairstyle",
    "undercut hairstyle",
    "updo hairstyle",
}
HAIRCLIP_DEFAULT_HAIRSTYLE = "short hair hairstyle"
HAIRCLIP_KEYWORD_TO_HAIRSTYLE = (
    ("afro", "afro hairstyle"),
    ("bob", "bob cut hairstyle"),
    ("bowl", "bowl cut hairstyle"),
    ("braid", "braid hairstyle"),
    ("caesar", "caesar cut hairstyle"),
    ("chignon", "chignon hairstyle"),
    ("cornrow", "cornrows hairstyle"),
    ("crew", "crew cut hairstyle"),
    ("crown braid", "crown braid hairstyle"),
    ("curtain", "curtained hair hairstyle"),
    ("dread", "dreadlocks hairstyle"),
    ("fade", "fade hairstyle"),
    ("fauxhawk", "fauxhawk hairstyle"),
    ("finger wave", "finger waves hairstyle"),
    ("french braid", "french braid hairstyle"),
    ("frosted", "frosted tips hairstyle"),
    ("mohawk", "mohawk hairstyle"),
    ("perm", "perm hairstyle"),
    ("pixie", "pixie cut hairstyle"),
    ("quiff", "quiff hairstyle"),
    ("ringlet", "ringlets hairstyle"),
    ("slick back", "slicked-back hairstyle"),
    ("spiky", "spiky hair hairstyle"),
    ("surfer", "surfer hair hairstyle"),
    ("taper", "taper cut hairstyle"),
    ("undercut", "undercut hairstyle"),
    ("updo", "updo hairstyle"),
)


def configured_provider_name() -> str:
    return str(getattr(settings, "AI_PLAYGROUND_PROVIDER", "stub")).strip().lower() or "stub"


def generate_hair_preview(
    *,
    selfie_path: str,
    reference_path: str,
    beard_reference_path: str | None = None,
    style_description: str = "",
    hair_color_name: str = "",
    beard_color_name: str = "",
    apply_beard_edit: bool = False,
    prompt_mode: str = PROMPT_MODE_CATALOG,
    expert_preferences: dict[str, str] | None = None,
    provider_override: str = "",
) -> PlaygroundImageResult:
    provider_name = str(provider_override or "").strip().lower() or configured_provider_name()
    provider = _provider_factory(provider_name)
    return provider.generate(
        selfie_path=selfie_path,
        reference_path=reference_path,
        beard_reference_path=beard_reference_path,
        style_description=style_description,
        hair_color_name=hair_color_name,
        beard_color_name=beard_color_name,
        apply_beard_edit=apply_beard_edit,
        prompt_mode=prompt_mode,
        expert_preferences=expert_preferences,
    )


def _provider_factory(provider_name: str):
    if provider_name == "nanobanana":
        return NanobananaProvider()
    if provider_name == "grok":
        return GrokImagesProvider()
    if provider_name in {"replicate_hairclip", "hairclip"}:
        if not bool(getattr(settings, "AI_PLAYGROUND_REPLICATE_HAIRCLIP_ENABLED", False)):
            raise PlaygroundProviderError(
                "Replicate HairCLIP provider is disabled. "
                "Set AI_PLAYGROUND_REPLICATE_HAIRCLIP_ENABLED=1 to enable testing."
            )
        return ReplicateHairCLIPProvider()
    if provider_name in {"hf_hairfastgan", "hairfastgan"}:
        if not bool(getattr(settings, "AI_PLAYGROUND_HF_HAIRFASTGAN_ENABLED", False)):
            raise PlaygroundProviderError(
                "Hugging Face HairFastGAN provider is disabled. "
                "Set AI_PLAYGROUND_HF_HAIRFASTGAN_ENABLED=1 to enable testing."
            )
        return HairFastGANProvider()
    if provider_name == "stub":
        return StubProvider()
    raise PlaygroundProviderError(
        f"Unsupported provider '{provider_name}'. "
        "Set AI_PLAYGROUND_PROVIDER to one of: nanobanana, grok, replicate_hairclip, hf_hairfastgan, stub."
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


def _get_json(url: str, headers: dict[str, str], timeout_seconds: int) -> dict[str, Any]:
    request = Request(url=url, headers=headers, method="GET")
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


def _image_file_as_data_url(
    file_path: str,
    *,
    max_side: int = 1024,
    jpeg_quality: int = 90,
) -> str:
    with Image.open(file_path) as raw_image:
        image = raw_image.convert("RGB")
        if max(image.width, image.height) > max_side:
            ratio = max_side / float(max(image.width, image.height))
            width = max(1, int(image.width * ratio))
            height = max(1, int(image.height * ratio))
            image = image.resize((width, height), Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=jpeg_quality, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"


def _decode_base64_payload(raw_value: str) -> bytes:
    try:
        return base64.b64decode(raw_value)
    except (ValueError, TypeError) as error:
        raise PlaygroundProviderError("Provider returned invalid base64 image payload.") from error


def _coerce_filepath(raw_value: Any, *, context: str) -> str:
    if isinstance(raw_value, str) and raw_value.strip():
        return raw_value
    if isinstance(raw_value, (tuple, list)) and raw_value:
        first = raw_value[0]
        if isinstance(first, str) and first.strip():
            return first
    raise PlaygroundProviderError(f"{context} did not return a valid image filepath.")


def _load_hairfastgan_client_dependencies():
    try:
        import gradio_client
    except ImportError as error:
        raise PlaygroundProviderError(
            "gradio_client is not installed. Run: pip install -r requirements.txt"
        ) from error

    client_cls = getattr(gradio_client, "Client", None)
    file_helper = getattr(gradio_client, "handle_file", None) or getattr(gradio_client, "file", None)
    if client_cls is None or file_helper is None:
        raise PlaygroundProviderError(
            "gradio_client is missing required APIs (Client/file). "
            "Install a recent gradio_client package."
        )
    return client_cls, file_helper


def _is_retryable_hairfastgan_error(error: Exception) -> bool:
    error_text = str(error).strip().lower()
    if not error_text:
        return False
    retry_markers = (
        "the upstream gradio app has raised an exception",
        "service unavailable",
        "temporarily unavailable",
        "deadline exceeded",
        "connection reset",
    )
    return any(marker in error_text for marker in retry_markers)


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


def _normalized_style_text(raw_text: str) -> str:
    if not raw_text:
        return ""
    normalized = raw_text.strip().lower().replace("-", " ")
    normalized = re.sub(r"[^a-z0-9\s]+", " ", normalized)
    return " ".join(normalized.split())


def _resolve_hairclip_hairstyle(raw_text: str) -> str | None:
    normalized = _normalized_style_text(raw_text)
    if not normalized:
        return None
    if normalized in HAIRCLIP_SUPPORTED_HAIRSTYLES:
        return normalized
    with_suffix = f"{normalized} hairstyle"
    if with_suffix in HAIRCLIP_SUPPORTED_HAIRSTYLES:
        return with_suffix
    for keyword, hairstyle in HAIRCLIP_KEYWORD_TO_HAIRSTYLE:
        if keyword in normalized:
            return hairstyle
    return None


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


class HairFastGANProvider:
    provider = "hf_hairfastgan"

    def __init__(self):
        self.space_id = str(
            getattr(settings, "AI_PLAYGROUND_HF_HAIRFASTGAN_SPACE", "AIRI-Institute/HairFastGAN")
        ).strip() or "AIRI-Institute/HairFastGAN"
        self.hf_token = str(getattr(settings, "AI_PLAYGROUND_HF_HAIRFASTGAN_TOKEN", "")).strip()
        self.align = self._resolved_align(
            str(getattr(settings, "AI_PLAYGROUND_HF_HAIRFASTGAN_ALIGN", "Face,Shape,Color")).strip()
        )
        self.blending = self._resolved_blending(
            str(getattr(settings, "AI_PLAYGROUND_HF_HAIRFASTGAN_BLENDING", "Article")).strip()
        )
        self.poisson_iters = _safe_int(
            str(getattr(settings, "AI_PLAYGROUND_HF_HAIRFASTGAN_POISSON_ITERS", "0")).strip()
        )
        if self.poisson_iters is None:
            self.poisson_iters = 0
        self.poisson_erosion = _safe_int(
            str(getattr(settings, "AI_PLAYGROUND_HF_HAIRFASTGAN_POISSON_EROSION", "15")).strip()
        )
        if self.poisson_erosion is None:
            self.poisson_erosion = 15
        swap_max_retries = _safe_int(
            str(getattr(settings, "AI_PLAYGROUND_HF_HAIRFASTGAN_SWAP_MAX_RETRIES", "3")).strip()
        )
        self.swap_max_retries = 3 if swap_max_retries is None else max(1, swap_max_retries)
        self.timeout_seconds = int(getattr(settings, "AI_PLAYGROUND_PROVIDER_TIMEOUT_SECONDS", 120))

    @staticmethod
    def _resolved_align(raw_align: str) -> list[str]:
        if not raw_align:
            return list(HAIRFASTGAN_DEFAULT_ALIGN)
        normalized = [value.strip().title() for value in raw_align.split(",") if value.strip()]
        picked = [value for value in normalized if value in HAIRFASTGAN_ALIGN_OPTIONS]
        if not picked:
            return list(HAIRFASTGAN_DEFAULT_ALIGN)
        # Preserve canonical ordering expected by the space.
        return [value for value in HAIRFASTGAN_DEFAULT_ALIGN if value in picked]

    @staticmethod
    def _resolved_blending(raw_blending: str) -> str:
        normalized = raw_blending.strip()
        if normalized in HAIRFASTGAN_BLEND_OPTIONS:
            return normalized
        return "Article"

    def _build_client(self):
        client_cls, file_helper = _load_hairfastgan_client_dependencies()
        client_kwargs: dict[str, Any] = {}
        if self.hf_token:
            client_kwargs["hf_token"] = self.hf_token
        try:
            client = client_cls(self.space_id, **client_kwargs)
        except TypeError:
            # Backward compatibility for older gradio_client versions without hf_token argument.
            client = client_cls(self.space_id)
        return client, file_helper

    def _resize_input(self, client, file_helper, *, input_path: str, api_name: str) -> str:
        primary_align = list(self.align)
        fallback_align = [value for value in primary_align if value != "Face"]

        attempts = [primary_align]
        if fallback_align != primary_align:
            attempts.append(fallback_align)
        if [] not in attempts:
            attempts.append([])

        last_error: Exception | None = None
        for attempt_align in attempts:
            try:
                response = client.predict(
                    img=file_helper(input_path),
                    align=attempt_align,
                    api_name=api_name,
                )
                return _coerce_filepath(response, context=f"HairFastGAN {api_name}")
            except Exception as error:
                last_error = error

        message = f"HairFastGAN preprocessing failed at {api_name}."
        if last_error is not None:
            message = (
                f"{message} Last error: {last_error.__class__.__name__}: "
                f"{str(last_error)[:200]}"
            )
        raise PlaygroundProviderError(message) from last_error

    def generate(
        self,
        *,
        selfie_path: str,
        reference_path: str,
        beard_reference_path: str | None = None,
        style_description: str = "",
        hair_color_name: str = "",
        beard_color_name: str = "",
        apply_beard_edit: bool = False,
    ) -> PlaygroundImageResult:
        _ = style_description, hair_color_name, beard_color_name
        if apply_beard_edit or beard_reference_path:
            raise PlaygroundProviderError(
                "HairFastGAN test integration currently supports hairstyle edits only. "
                "Use beard style = None for this provider."
            )
        client, file_helper = self._build_client()

        face_path = self._resize_input(
            client,
            file_helper,
            input_path=selfie_path,
            api_name="/resize_inner",
        )
        shape_path = self._resize_input(
            client,
            file_helper,
            input_path=reference_path,
            api_name="/resize_inner_1",
        )
        color_path = self._resize_input(
            client,
            file_helper,
            input_path=reference_path,
            api_name="/resize_inner_2",
        )

        last_swap_error: Exception | None = None
        swap_response: Any = None
        for attempt_number in range(1, self.swap_max_retries + 1):
            try:
                swap_response = client.predict(
                    face=file_helper(face_path),
                    shape=file_helper(shape_path),
                    color=file_helper(color_path),
                    blending=self.blending,
                    poisson_iters=float(self.poisson_iters),
                    poisson_erosion=float(self.poisson_erosion),
                    api_name="/swap_hair",
                )
                break
            except Exception as error:
                last_swap_error = error
                retryable_error = _is_retryable_hairfastgan_error(error)
                if attempt_number >= self.swap_max_retries or not retryable_error:
                    if retryable_error and attempt_number >= self.swap_max_retries:
                        raise PlaygroundProviderError(
                            "HairFastGAN generation failed during /swap_hair after "
                            f"{self.swap_max_retries} attempts. "
                            "The upstream Space is currently rejecting this input combination or is unstable. "
                            f"{error.__class__.__name__}: {str(error)[:200]}"
                        ) from error
                    raise PlaygroundProviderError(
                        "HairFastGAN generation failed during /swap_hair. "
                        f"{error.__class__.__name__}: {str(error)[:200]}"
                    ) from error
                time.sleep(min(2 * attempt_number, 4))
                client, file_helper = self._build_client()

        if swap_response is None and last_swap_error is not None:
            raise PlaygroundProviderError(
                "HairFastGAN generation failed during /swap_hair. "
                f"{last_swap_error.__class__.__name__}: {str(last_swap_error)[:200]}"
            ) from last_swap_error

        output_path: str
        output_error = ""
        if isinstance(swap_response, (tuple, list)):
            output_path = _coerce_filepath(swap_response[0], context="HairFastGAN /swap_hair")
            if len(swap_response) > 1 and isinstance(swap_response[1], str):
                output_error = swap_response[1].strip()
        else:
            output_path = _coerce_filepath(swap_response, context="HairFastGAN /swap_hair")

        if output_error:
            raise PlaygroundProviderError(f"HairFastGAN returned an error: {output_error[:180]}")

        if output_path.startswith(("http://", "https://")):
            image_bytes, mime_type = _download_binary(output_path, self.timeout_seconds)
        else:
            if not os.path.exists(output_path):
                raise PlaygroundProviderError("HairFastGAN returned an output path that does not exist.")
            with open(output_path, "rb") as file_obj:
                image_bytes = file_obj.read()
            mime_type = _guess_mime_type(output_path)

        return PlaygroundImageResult(
            image_bytes=image_bytes,
            mime_type=mime_type,
            provider=self.provider,
        )


class ReplicateHairCLIPProvider:
    provider = "replicate_hairclip"

    def __init__(self):
        self.api_token = str(getattr(settings, "AI_PLAYGROUND_REPLICATE_API_TOKEN", "")).strip()
        self.api_base = str(
            getattr(settings, "AI_PLAYGROUND_REPLICATE_API_BASE", "https://api.replicate.com/v1")
        ).strip() or "https://api.replicate.com/v1"
        self.model_version = str(
            getattr(
                settings,
                "AI_PLAYGROUND_REPLICATE_HAIRCLIP_MODEL_VERSION",
                "b95cb2a16763bea87ed7ed851d5a3ab2f4655e94bcfb871edba029d4814fa587",
            )
        ).strip() or "b95cb2a16763bea87ed7ed851d5a3ab2f4655e94bcfb871edba029d4814fa587"
        resolved_fallback = _resolve_hairclip_hairstyle(
            str(
                getattr(
                    settings,
                    "AI_PLAYGROUND_REPLICATE_HAIRCLIP_FALLBACK_HAIRSTYLE",
                    HAIRCLIP_DEFAULT_HAIRSTYLE,
                )
            ).strip()
        )
        self.fallback_hairstyle = resolved_fallback or HAIRCLIP_DEFAULT_HAIRSTYLE

        wait_seconds = _safe_int(
            str(getattr(settings, "AI_PLAYGROUND_REPLICATE_HAIRCLIP_WAIT_SECONDS", "60")).strip()
        )
        if wait_seconds is None:
            wait_seconds = 60
        self.wait_seconds = max(1, min(wait_seconds, 60))

        poll_interval = _safe_float(
            str(getattr(settings, "AI_PLAYGROUND_REPLICATE_HAIRCLIP_POLL_INTERVAL_SECONDS", "2")).strip(),
            default=2.0,
        )
        self.poll_interval_seconds = max(0.5, min(float(poll_interval), 10.0))

        max_image_side = _safe_int(
            str(getattr(settings, "AI_PLAYGROUND_REPLICATE_HAIRCLIP_MAX_IMAGE_SIDE", "1024")).strip()
        )
        self.max_image_side = 1024 if max_image_side is None else max(512, min(max_image_side, 2048))

        jpeg_quality = _safe_int(
            str(getattr(settings, "AI_PLAYGROUND_REPLICATE_HAIRCLIP_JPEG_QUALITY", "90")).strip()
        )
        if jpeg_quality is None:
            jpeg_quality = 90
        self.jpeg_quality = max(40, min(jpeg_quality, 95))

        self.timeout_seconds = int(getattr(settings, "AI_PLAYGROUND_PROVIDER_TIMEOUT_SECONDS", 120))
        self.predictions_endpoint = f"{self.api_base.rstrip('/')}/predictions"

    def _auth_headers(self, *, include_wait_preference: bool = False) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.api_token}"}
        if include_wait_preference:
            headers["Prefer"] = f"wait={self.wait_seconds}"
        return headers

    def _build_prediction_input(
        self,
        *,
        image_data_url: str,
        style_description: str,
        hair_color_name: str,
    ) -> dict[str, Any]:
        hairstyle = _resolve_hairclip_hairstyle(style_description) or self.fallback_hairstyle
        color_text = hair_color_name.strip()

        if color_text:
            editing_type = "both"
        else:
            editing_type = "hairstyle"

        payload: dict[str, Any] = {
            "image": image_data_url,
            "editing_type": editing_type,
            "hairstyle_description": hairstyle,
        }
        if color_text:
            payload["color_description"] = color_text
        return payload

    def _resolve_get_url(self, created_prediction: dict[str, Any]) -> str:
        urls = created_prediction.get("urls")
        if isinstance(urls, dict):
            get_url = urls.get("get")
            if isinstance(get_url, str) and get_url.strip():
                return get_url

        prediction_id = created_prediction.get("id")
        if isinstance(prediction_id, str) and prediction_id.strip():
            return f"{self.predictions_endpoint}/{prediction_id.strip()}"

        raise PlaygroundProviderError("Replicate HairCLIP did not return a prediction poll URL.")

    def _await_prediction(self, get_url: str) -> dict[str, Any]:
        deadline = time.time() + self.timeout_seconds
        while True:
            prediction = _get_json(
                get_url,
                headers=self._auth_headers(),
                timeout_seconds=self.timeout_seconds,
            )
            status = str(prediction.get("status", "")).strip().lower()
            if status in {"succeeded", "failed", "canceled"}:
                return prediction

            if time.time() >= deadline:
                raise PlaygroundProviderError(
                    "Replicate HairCLIP request timed out while waiting for prediction completion."
                )
            time.sleep(self.poll_interval_seconds)

    def generate(
        self,
        *,
        selfie_path: str,
        reference_path: str,
        beard_reference_path: str | None = None,
        style_description: str = "",
        hair_color_name: str = "",
        beard_color_name: str = "",
        apply_beard_edit: bool = False,
    ) -> PlaygroundImageResult:
        _ = reference_path, beard_color_name
        if apply_beard_edit or beard_reference_path:
            raise PlaygroundProviderError(
                "Replicate HairCLIP integration supports hairstyle edits only. "
                "Use beard style = None for this provider."
            )
        if not self.api_token:
            raise PlaygroundProviderError(
                "Replicate API token is missing. Set AI_PLAYGROUND_REPLICATE_API_TOKEN."
            )

        image_data_url = _image_file_as_data_url(
            selfie_path,
            max_side=self.max_image_side,
            jpeg_quality=self.jpeg_quality,
        )
        create_payload = {
            "version": self.model_version,
            "input": self._build_prediction_input(
                image_data_url=image_data_url,
                style_description=style_description,
                hair_color_name=hair_color_name,
            ),
        }
        created_prediction = _post_json(
            self.predictions_endpoint,
            create_payload,
            headers=self._auth_headers(include_wait_preference=True),
            timeout_seconds=self.timeout_seconds,
        )
        prediction_status = str(created_prediction.get("status", "")).strip().lower()
        if prediction_status in {"starting", "processing"}:
            get_url = self._resolve_get_url(created_prediction)
            created_prediction = self._await_prediction(get_url)
            prediction_status = str(created_prediction.get("status", "")).strip().lower()

        if prediction_status != "succeeded":
            error_text = str(created_prediction.get("error") or "Unknown provider error.").strip()
            raise PlaygroundProviderError(
                "Replicate HairCLIP generation failed. "
                f"{error_text[:200]}"
            )

        output_url = _coerce_filepath(
            created_prediction.get("output"),
            context="Replicate HairCLIP output",
        )
        if not output_url.startswith(("http://", "https://")):
            raise PlaygroundProviderError(
                "Replicate HairCLIP returned an output reference that is not a downloadable URL."
            )
        image_bytes, mime_type = _download_binary(output_url, self.timeout_seconds)
        return PlaygroundImageResult(
            image_bytes=image_bytes,
            mime_type=mime_type,
            provider=self.provider,
        )


class StubProvider:
    provider = "stub"

    def generate(
        self,
        *,
        selfie_path: str,
        reference_path: str,
        beard_reference_path: str | None = None,
        style_description: str = "",
        hair_color_name: str = "",
        beard_color_name: str = "",
        apply_beard_edit: bool = False,
        prompt_mode: str = PROMPT_MODE_CATALOG,
        expert_preferences: dict[str, str] | None = None,
    ) -> PlaygroundImageResult:
        _ = (
            beard_reference_path,
            style_description,
            hair_color_name,
            beard_color_name,
            apply_beard_edit,
            prompt_mode,
            expert_preferences,
        )
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
        style_description: str = "",
        hair_color_name: str = "",
        beard_color_name: str = "",
        apply_beard_edit: bool = False,
        prompt_mode: str = PROMPT_MODE_CATALOG,
        expert_preferences: dict[str, str] | None = None,
    ) -> PlaygroundImageResult:
        if not self.api_key:
            raise PlaygroundProviderError("Nanobanana API key is missing.")

        resolved_prompt_style = self._resolved_prompt_style()
        resolved_prompt_set = self._resolved_prompt_set()
        is_expert_mode = str(prompt_mode or "").strip().lower() == PROMPT_MODE_EXPERT

        selfie_mime, selfie_b64 = _image_file_as_base64(selfie_path)
        beard_mime = ""
        beard_b64 = ""
        if beard_reference_path:
            beard_mime, beard_b64 = _image_file_as_base64(beard_reference_path)

        content_parts = [
            {"text": "Image 1 (identity anchor selfie):" if not is_expert_mode else "Image 1 (subject selfie for expert haircut analysis):"},
            {"inlineData": {"mimeType": selfie_mime, "data": selfie_b64}},
        ]
        if not is_expert_mode:
            reference_mime, reference_b64 = _image_file_as_base64(reference_path)
            content_parts.extend(
                [
                    {"text": "Image 2 (target hairstyle reference):"},
                    {"inlineData": {"mimeType": reference_mime, "data": reference_b64}},
                ]
            )
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
                    style_description=style_description,
                    hair_color_name=hair_color_name,
                    beard_color_name=beard_color_name,
                    apply_beard_edit=apply_beard_edit,
                    prompt_style=resolved_prompt_style,
                    prompt_set=resolved_prompt_set,
                    prompt_mode=prompt_mode,
                    expert_preferences=expert_preferences,
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
        style_description: str = "",
        hair_color_name: str = "",
        beard_color_name: str = "",
        apply_beard_edit: bool = False,
        prompt_mode: str = PROMPT_MODE_CATALOG,
        expert_preferences: dict[str, str] | None = None,
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
                style_description=style_description,
                hair_color_name=hair_color_name,
                beard_color_name=beard_color_name,
                apply_beard_edit=apply_beard_edit,
                prompt_style=PROMPT_STYLE_PRO,
                prompt_mode=prompt_mode,
                expert_preferences=expert_preferences,
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
