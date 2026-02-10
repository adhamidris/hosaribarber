import hashlib
from datetime import timedelta
from time import perf_counter

from django.conf import settings
from django.core import signing
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import (
    PlaygroundBeardStyle,
    PlaygroundColorOption,
    PlaygroundColorScopeChoices,
    PlaygroundGeneration,
    PlaygroundGenerationStatusChoices,
    PlaygroundRateLimitActionChoices,
    PlaygroundRateLimitEvent,
    PlaygroundSession,
    PlaygroundStyle,
)
from .services import (
    PlaygroundProviderError,
    configured_provider_name,
    extension_from_mime,
    generate_hair_preview,
)

SESSION_COOKIE_NAME = getattr(
    settings,
    "AI_PLAYGROUND_SESSION_COOKIE_NAME",
    "ai_playground_session",
)
SESSION_COOKIE_SALT = "ai_playground.session"
SESSION_DURATION_MINUTES = int(getattr(settings, "AI_PLAYGROUND_SESSION_DURATION_MINUTES", 30))
SESSION_MAX_AGE_SECONDS = SESSION_DURATION_MINUTES * 60
SESSION_COOKIE_SECURE = bool(getattr(settings, "AI_PLAYGROUND_SESSION_COOKIE_SECURE", not settings.DEBUG))
ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
NONE_SELECTION_VALUE = "none"

SESSION_REQUIRED_MESSAGE = "Session expired. Scan the QR code again."


def _int_setting(name: str, default: int) -> int:
    try:
        return int(getattr(settings, name, default))
    except (TypeError, ValueError):
        return default


def _bool_setting(name: str, default: bool) -> bool:
    value = getattr(settings, name, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _client_ip(request: HttpRequest) -> str:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    remote_address = request.META.get("REMOTE_ADDR", "")
    return remote_address or "0.0.0.0"


def _signed_session_value(session_token: str) -> str:
    return signing.dumps(session_token, salt=SESSION_COOKIE_SALT)


def _read_session_cookie(request: HttpRequest) -> str | None:
    raw_value = request.COOKIES.get(SESSION_COOKIE_NAME)
    if not raw_value:
        return None
    try:
        return signing.loads(raw_value, salt=SESSION_COOKIE_SALT, max_age=SESSION_MAX_AGE_SECONDS)
    except signing.BadSignature:
        return None


def _set_session_cookie(response: HttpResponse, session: PlaygroundSession):
    response.set_cookie(
        SESSION_COOKIE_NAME,
        _signed_session_value(session.token),
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="Lax",
    )


def _clear_session_cookie(response: HttpResponse):
    response.delete_cookie(SESSION_COOKIE_NAME)


def _get_active_session(request: HttpRequest) -> PlaygroundSession | None:
    session_token = _read_session_cookie(request)
    if not session_token:
        return None
    session = PlaygroundSession.objects.filter(token=session_token).first()
    if session is None or not session.is_active:
        return None
    return session


def _session_required_response() -> JsonResponse:
    response = JsonResponse({"ok": False, "error": SESSION_REQUIRED_MESSAGE}, status=401)
    _clear_session_cookie(response)
    response["Cache-Control"] = "no-store"
    return response


def _rate_limited_response(message: str, retry_after_seconds: int | None = None) -> JsonResponse:
    response = JsonResponse({"ok": False, "error": message}, status=429)
    if retry_after_seconds is not None and retry_after_seconds > 0:
        response["Retry-After"] = str(retry_after_seconds)
    response["Cache-Control"] = "no-store"
    return response


def _record_rate_limit_event(
    *,
    action: str,
    ip_address: str,
    session: PlaygroundSession | None = None,
):
    if not ip_address:
        return
    PlaygroundRateLimitEvent.objects.create(
        action=action,
        ip_address=ip_address,
        session=session,
    )


def _is_ip_rate_limited(*, action: str, ip_address: str, limit_per_hour: int) -> bool:
    if not ip_address or limit_per_hour <= 0:
        return False
    window_start = timezone.now() - timedelta(hours=1)
    recent_count = PlaygroundRateLimitEvent.objects.filter(
        action=action,
        ip_address=ip_address,
        created_at__gte=window_start,
    ).count()
    return recent_count >= limit_per_hour


def _validate_uploaded_image(image):
    max_image_size_bytes = _int_setting("AI_PLAYGROUND_MAX_IMAGE_SIZE_BYTES", 6 * 1024 * 1024)
    if image is None:
        return "No image was provided."
    if image.content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        return "Unsupported image format. Use JPEG, PNG, or WEBP."
    if image.size > max_image_size_bytes:
        max_mb = max_image_size_bytes // (1024 * 1024)
        return f"Image is too large. Maximum allowed size is {max_mb} MB."
    return ""


def _uploaded_file_sha256(uploaded_file) -> str:
    hasher = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        hasher.update(chunk)
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)
    return hasher.hexdigest()


def _active_color_options(scope: str):
    return PlaygroundColorOption.objects.filter(
        is_active=True,
    ).filter(
        Q(scope=scope) | Q(scope=PlaygroundColorScopeChoices.BOTH),
    ).order_by("sort_order", "id")


def _parse_choice_value(raw_value: str) -> tuple[str, bool]:
    normalized = (raw_value or "").strip()
    if not normalized:
        return "", False
    return normalized, True


def _generation_payload(generation: PlaygroundGeneration, session_generation_count: int) -> dict:
    style = generation.style
    beard_style = generation.beard_style
    hair_color = generation.hair_color_option
    beard_color = generation.beard_color_option
    return {
        "id": generation.id,
        "status": generation.status,
        "provider": generation.provider,
        "created_at": generation.created_at.isoformat(),
        "processing_ms": generation.processing_ms,
        "session_generation_count": session_generation_count,
        "source": "curated" if style else "custom",
        "style_name": style.name if style and style.name else "",
        "beard_style_name": beard_style.name if beard_style and beard_style.name else "",
        "hair_color_name": hair_color.name if hair_color else "",
        "beard_color_name": beard_color.name if beard_color else "",
        "result_url": generation.result_image.url if generation.result_image else "",
    }


@require_GET
def start_session(request: HttpRequest):
    ip_address = _client_ip(request)
    start_rate_limit_per_ip_per_hour = _int_setting("AI_PLAYGROUND_START_MAX_PER_IP_PER_HOUR", 120)
    if _is_ip_rate_limited(
        action=PlaygroundRateLimitActionChoices.START,
        ip_address=ip_address,
        limit_per_hour=start_rate_limit_per_ip_per_hour,
    ):
        return _rate_limited_response(
            "Too many session starts from this network. Please wait and retry.",
            retry_after_seconds=60,
        )

    now = timezone.now()
    session = PlaygroundSession.objects.create(
        expires_at=now + timedelta(minutes=SESSION_DURATION_MINUTES),
        last_ip=ip_address,
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
    )
    _record_rate_limit_event(
        action=PlaygroundRateLimitActionChoices.START,
        ip_address=ip_address,
        session=session,
    )
    response = redirect("ai-playground-home")
    _set_session_cookie(response, session)
    response["Cache-Control"] = "no-store"
    return response


@require_GET
def playground_home(request: HttpRequest):
    session = _get_active_session(request)
    if session is None:
        response = render(
            request,
            "ai_playground/session_required.html",
            {
                "start_url": "ai-playground-start",
                "session_duration_minutes": SESSION_DURATION_MINUTES,
            },
            status=401,
        )
        _clear_session_cookie(response)
        response["Cache-Control"] = "no-store"
        return response

    session.touch(
        ip_address=_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )
    session.save(update_fields=["last_seen_at", "last_ip", "user_agent"])

    styles = PlaygroundStyle.objects.filter(is_active=True).order_by("sort_order", "id")
    beard_styles = PlaygroundBeardStyle.objects.filter(is_active=True).order_by("sort_order", "id")
    hair_colors = _active_color_options(PlaygroundColorScopeChoices.HAIR)
    beard_colors = _active_color_options(PlaygroundColorScopeChoices.BEARD)
    recent_generations = list(
        PlaygroundGeneration.objects.filter(
            session=session,
            status=PlaygroundGenerationStatusChoices.SUCCEEDED,
        )
        .exclude(result_image="")
        .select_related("style", "beard_style", "hair_color_option", "beard_color_option")
        .order_by("-created_at")[:8]
    )
    latest_generation = recent_generations[0] if recent_generations else None

    response = render(
        request,
        "ai_playground/playground_home.html",
        {
            "active_session": session,
            "styles": styles,
            "beard_styles": beard_styles,
            "hair_colors": hair_colors,
            "beard_colors": beard_colors,
            "latest_generation": latest_generation,
            "recent_generations": recent_generations,
        },
    )
    response["Cache-Control"] = "no-store"
    return response


@require_GET
def styles_api(request: HttpRequest):
    session = _get_active_session(request)
    if session is None:
        return _session_required_response()

    styles = PlaygroundStyle.objects.filter(is_active=True).order_by("sort_order", "id")
    beard_styles = PlaygroundBeardStyle.objects.filter(is_active=True).order_by("sort_order", "id")
    hair_colors = _active_color_options(PlaygroundColorScopeChoices.HAIR)
    beard_colors = _active_color_options(PlaygroundColorScopeChoices.BEARD)
    style_payload = [
        {
            "id": style.id,
            "name": style.name,
            "image_url": style.image.url,
        }
        for style in styles
    ]
    beard_payload = [
        {
            "id": style.id,
            "name": style.name,
            "image_url": style.image.url,
        }
        for style in beard_styles
    ]
    hair_color_payload = [
        {
            "id": color.id,
            "name": color.name,
            "hex_code": color.hex_code,
        }
        for color in hair_colors
    ]
    beard_color_payload = [
        {
            "id": color.id,
            "name": color.name,
            "hex_code": color.hex_code,
        }
        for color in beard_colors
    ]

    session.touch(
        ip_address=_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )
    session.save(update_fields=["last_seen_at", "last_ip", "user_agent"])

    response = JsonResponse(
        {
            "ok": True,
            "styles": style_payload,
            "beard_styles": beard_payload,
            "hair_colors": hair_color_payload,
            "beard_colors": beard_color_payload,
            "has_selfie": session.has_selfie,
            "expires_at": session.expires_at.isoformat(),
        }
    )
    response["Cache-Control"] = "no-store"
    return response


@require_POST
def upload_selfie(request: HttpRequest):
    session = _get_active_session(request)
    if session is None:
        return _session_required_response()

    image = request.FILES.get("image")
    error = _validate_uploaded_image(image)
    if error:
        return JsonResponse({"ok": False, "error": error}, status=400)

    if session.selfie_image:
        session.selfie_image.delete(save=False)

    session.selfie_image = image
    session.selfie_uploaded_at = timezone.now()
    session.touch(
        ip_address=_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )
    session.save(
        update_fields=[
            "selfie_image",
            "selfie_uploaded_at",
            "last_seen_at",
            "last_ip",
            "user_agent",
        ]
    )

    response = JsonResponse(
        {
            "ok": True,
            "selfie": {
                "url": session.selfie_image.url,
                "uploaded_at": session.selfie_uploaded_at.isoformat(),
            },
            "expires_at": session.expires_at.isoformat(),
        }
    )
    response["Cache-Control"] = "no-store"
    return response


@require_POST
def generate_preview(request: HttpRequest):
    session = _get_active_session(request)
    if session is None:
        return _session_required_response()
    if not session.has_selfie:
        return JsonResponse({"ok": False, "error": "Upload a selfie first."}, status=400)
    ip_address = _client_ip(request)
    generate_rate_limit_per_ip_per_hour = _int_setting("AI_PLAYGROUND_GENERATE_MAX_PER_IP_PER_HOUR", 60)
    session_generation_limit = _int_setting("AI_PLAYGROUND_SESSION_GENERATION_LIMIT", 5)
    generate_min_interval_seconds = _int_setting("AI_PLAYGROUND_MIN_GENERATE_INTERVAL_SECONDS", 10)
    one_style_per_session = _bool_setting("AI_PLAYGROUND_ONE_STYLE_PER_SESSION", True)

    style_id_value = request.POST.get("style_id", "").strip()
    custom_style_image = request.FILES.get("custom_style_image")
    hair_color_value, has_hair_color_choice = _parse_choice_value(request.POST.get("hair_color_option_id", ""))
    beard_style_value, has_beard_style_choice = _parse_choice_value(request.POST.get("beard_style_id", ""))
    beard_color_value, has_beard_color_choice = _parse_choice_value(request.POST.get("beard_color_option_id", ""))

    if not has_hair_color_choice:
        return JsonResponse({"ok": False, "error": "Choose a hair color option first."}, status=400)
    if not has_beard_style_choice:
        return JsonResponse({"ok": False, "error": "Choose a beard style option first."}, status=400)
    if not has_beard_color_choice:
        return JsonResponse({"ok": False, "error": "Choose a beard color option first."}, status=400)

    if style_id_value and custom_style_image:
        return JsonResponse(
            {"ok": False, "error": "Choose either a curated style or upload a custom style, not both."},
            status=400,
        )
    if not style_id_value and not custom_style_image:
        return JsonResponse(
            {"ok": False, "error": "Select a hairstyle or upload a custom haircut image."},
            status=400,
        )

    style = None
    beard_style = None
    hair_color_option = None
    beard_color_option = None
    custom_style_fingerprint = ""

    if style_id_value:
        try:
            style_id = int(style_id_value)
        except ValueError:
            return JsonResponse({"ok": False, "error": "Invalid hairstyle selection."}, status=400)
        style = PlaygroundStyle.objects.filter(id=style_id, is_active=True).first()
        if style is None:
            return JsonResponse({"ok": False, "error": "Selected hairstyle is unavailable."}, status=404)

    normalized_hair_color = hair_color_value.lower()
    if normalized_hair_color != NONE_SELECTION_VALUE:
        try:
            hair_color_id = int(hair_color_value)
        except ValueError:
            return JsonResponse({"ok": False, "error": "Invalid hair color selection."}, status=400)
        hair_color_option = _active_color_options(PlaygroundColorScopeChoices.HAIR).filter(id=hair_color_id).first()
        if hair_color_option is None:
            return JsonResponse({"ok": False, "error": "Selected hair color is unavailable."}, status=404)

    normalized_beard_style = beard_style_value.lower()
    if normalized_beard_style != NONE_SELECTION_VALUE:
        try:
            beard_style_id = int(beard_style_value)
        except ValueError:
            return JsonResponse({"ok": False, "error": "Invalid beard style selection."}, status=400)
        beard_style = PlaygroundBeardStyle.objects.filter(id=beard_style_id, is_active=True).first()
        if beard_style is None:
            return JsonResponse({"ok": False, "error": "Selected beard style is unavailable."}, status=404)

    normalized_beard_color = beard_color_value.lower()
    if normalized_beard_color != NONE_SELECTION_VALUE:
        try:
            beard_color_id = int(beard_color_value)
        except ValueError:
            return JsonResponse({"ok": False, "error": "Invalid beard color selection."}, status=400)
        beard_color_option = _active_color_options(PlaygroundColorScopeChoices.BEARD).filter(id=beard_color_id).first()
        if beard_color_option is None:
            return JsonResponse({"ok": False, "error": "Selected beard color is unavailable."}, status=404)

    if beard_style is None and beard_color_option is not None:
        return JsonResponse(
            {"ok": False, "error": "Choose a beard style before applying beard color."},
            status=400,
        )

    if custom_style_image:
        error = _validate_uploaded_image(custom_style_image)
        if error:
            return JsonResponse({"ok": False, "error": error}, status=400)
        custom_style_fingerprint = _uploaded_file_sha256(custom_style_image)

    with transaction.atomic():
        locked_session = PlaygroundSession.objects.select_for_update().get(id=session.id)
        locked_selfie_name = locked_session.selfie_image.name

        existing_generation = None
        if style is not None:
            existing_generation = (
                PlaygroundGeneration.objects.filter(
                    session=locked_session,
                    style=style,
                    beard_style=beard_style,
                    hair_color_option=hair_color_option,
                    beard_color_option=beard_color_option,
                    selfie_image=locked_selfie_name,
                    status=PlaygroundGenerationStatusChoices.SUCCEEDED,
                )
                .exclude(result_image="")
                .order_by("-created_at")
                .first()
            )
        elif custom_style_fingerprint:
            existing_generation = (
                PlaygroundGeneration.objects.filter(
                    session=locked_session,
                    style__isnull=True,
                    custom_style_fingerprint=custom_style_fingerprint,
                    beard_style=beard_style,
                    hair_color_option=hair_color_option,
                    beard_color_option=beard_color_option,
                    selfie_image=locked_selfie_name,
                    status=PlaygroundGenerationStatusChoices.SUCCEEDED,
                )
                .exclude(result_image="")
                .order_by("-created_at")
                .first()
            )
        if existing_generation is not None:
            locked_session.touch(
                ip_address=ip_address,
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
            locked_session.save(update_fields=["last_seen_at", "last_ip", "user_agent"])
            response = JsonResponse(
                {
                    "ok": True,
                    "reused": True,
                    "message": "Using existing preview from this session.",
                    "generation": _generation_payload(
                        existing_generation,
                        session_generation_count=locked_session.generation_count,
                    ),
                }
            )
            response["Cache-Control"] = "no-store"
            return response

        if _is_ip_rate_limited(
            action=PlaygroundRateLimitActionChoices.GENERATE,
            ip_address=ip_address,
            limit_per_hour=generate_rate_limit_per_ip_per_hour,
        ):
            return _rate_limited_response(
                "Generation rate limit reached on this network. Please try again shortly.",
                retry_after_seconds=60,
            )

        if locked_session.generation_count >= session_generation_limit:
            return _rate_limited_response(
                "Session generation quota reached. Please rescan the QR code for a new session."
            )

        if generate_min_interval_seconds > 0 and locked_session.last_generation_at:
            elapsed_seconds = int((timezone.now() - locked_session.last_generation_at).total_seconds())
            if elapsed_seconds < generate_min_interval_seconds:
                retry_after = max(1, generate_min_interval_seconds - elapsed_seconds)
                return _rate_limited_response(
                    "Please wait a few seconds before starting another generation.",
                    retry_after_seconds=retry_after,
                )

        if style is not None and one_style_per_session:
            already_used = (
                PlaygroundGeneration.objects.filter(
                    session=locked_session,
                    style=style,
                    beard_style=beard_style,
                    hair_color_option=hair_color_option,
                    beard_color_option=beard_color_option,
                    selfie_image=locked_selfie_name,
                    status=PlaygroundGenerationStatusChoices.SUCCEEDED,
                )
                .order_by("-created_at")
                .first()
            )
            if already_used is not None:
                return JsonResponse(
                    {
                        "ok": False,
                        "error": "This style was already used, but no reusable preview is available.",
                    },
                    status=409,
                )

        locked_session.touch(
            ip_address=ip_address,
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        locked_session.generation_count += 1
        locked_session.last_generation_at = timezone.now()
        locked_session.save(
            update_fields=[
                "generation_count",
                "last_generation_at",
                "last_seen_at",
                "last_ip",
                "user_agent",
            ]
        )
        current_generation_count = locked_session.generation_count

        generation = PlaygroundGeneration.objects.create(
            session=locked_session,
            style=style,
            beard_style=beard_style,
            hair_color_option=hair_color_option,
            beard_color_option=beard_color_option,
            selfie_image=locked_session.selfie_image.name,
            custom_style_image=custom_style_image,
            custom_style_fingerprint=custom_style_fingerprint,
            provider=configured_provider_name(),
            status=PlaygroundGenerationStatusChoices.PENDING,
        )
        _record_rate_limit_event(
            action=PlaygroundRateLimitActionChoices.GENERATE,
            ip_address=ip_address,
            session=locked_session,
        )

    started = perf_counter()
    try:
        reference_path = (
            style.image.path
            if style is not None
            else generation.custom_style_image.path
        )
        beard_reference_path = beard_style.image.path if beard_style is not None else None
        provider_result = generate_hair_preview(
            selfie_path=generation.selfie_image.path,
            reference_path=reference_path,
            beard_reference_path=beard_reference_path,
            hair_color_name=hair_color_option.name if hair_color_option else "",
            beard_color_name=beard_color_option.name if beard_color_option else "",
            apply_beard_edit=beard_style is not None,
        )
        extension = extension_from_mime(provider_result.mime_type)
        result_filename = f"generation-{generation.id}.{extension}"
        generation.result_image.save(
            result_filename,
            ContentFile(provider_result.image_bytes),
            save=False,
        )
        generation.status = PlaygroundGenerationStatusChoices.SUCCEEDED
        generation.provider = provider_result.provider
        generation.processing_ms = int((perf_counter() - started) * 1000)
        generation.error_message = ""
        generation.save(update_fields=["status", "provider", "processing_ms", "error_message", "result_image", "updated_at"])
    except PlaygroundProviderError as error:
        generation.status = PlaygroundGenerationStatusChoices.FAILED
        generation.processing_ms = int((perf_counter() - started) * 1000)
        generation.error_message = str(error)[:255]
        generation.save(update_fields=["status", "processing_ms", "error_message", "updated_at"])
        return JsonResponse(
            {
                "ok": False,
                "error": "Generation failed. Please retry in a moment.",
                "provider": generation.provider,
                "details": str(error) if settings.DEBUG else "",
            },
            status=502,
        )

    response = JsonResponse(
        {
            "ok": True,
            "message": "Generation completed.",
            "generation": _generation_payload(
                generation,
                session_generation_count=current_generation_count,
            ),
        },
    )
    response["Cache-Control"] = "no-store"
    return response
