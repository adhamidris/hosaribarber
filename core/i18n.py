from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.urls import translate_url


NON_I18N_PATH_PREFIXES = (
    "/i18n/",
    "/ai-playground/",
    "/static/",
    "/media/",
)


def _normalize_language(code: str) -> str:
    return (code or "").split("-")[0]


def _strip_language_prefix(path: str, language_codes: list[str]) -> str:
    for language_code in language_codes:
        prefix = f"/{language_code}"
        if path == prefix:
            return "/"
        if path.startswith(f"{prefix}/"):
            return path[len(prefix) :]
    return path


def localize_url(url: str, language_code: str) -> str:
    if not url:
        return url

    target_language = _normalize_language(language_code)
    if not target_language:
        return url

    translated = translate_url(url, language_code)
    if translated and translated != url:
        return translated

    split_result = urlsplit(url)
    path = split_result.path or "/"
    if not path.startswith("/"):
        path = f"/{path}"

    if path == "/" or any(path.startswith(prefix) for prefix in NON_I18N_PATH_PREFIXES):
        return translated or url

    default_language = _normalize_language(settings.LANGUAGE_CODE)
    configured_languages = [_normalize_language(code) for code, _ in settings.LANGUAGES]
    non_default_languages = [code for code in configured_languages if code and code != default_language]
    canonical_path = _strip_language_prefix(path, non_default_languages)

    if target_language == default_language:
        localized_path = canonical_path
    else:
        localized_path = f"/{target_language}{canonical_path}"
        if canonical_path == "/":
            localized_path = f"/{target_language}/"

    return urlunsplit(
        (
            split_result.scheme,
            split_result.netloc,
            localized_path,
            split_result.query,
            split_result.fragment,
        )
    )
