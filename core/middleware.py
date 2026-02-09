from django.conf import settings
from django.http import HttpResponseRedirect
from django.utils import translation

from .i18n import localize_url
from .request_context import reset_current_user, set_current_user


class UserPreferredLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.allowed_languages = {code for code, _ in settings.LANGUAGES}

    def __call__(self, request):
        token = set_current_user(getattr(request, "user", None))
        previous_language = translation.get_language()

        try:
            if request.user.is_authenticated:
                preferred_language = request.user.preferred_language
                if preferred_language in self.allowed_languages:
                    translation.activate(preferred_language)
                    request.LANGUAGE_CODE = preferred_language
                    if request.method in {"GET", "HEAD"}:
                        current_full_path = request.get_full_path()
                        translated_path = localize_url(current_full_path, preferred_language)
                        if translated_path and translated_path != current_full_path:
                            response = HttpResponseRedirect(translated_path)
                            response.set_cookie(settings.LANGUAGE_COOKIE_NAME, preferred_language)
                            return response

            response = self.get_response(request)

            language_code = getattr(request, "LANGUAGE_CODE", None)
            if language_code:
                response.set_cookie(settings.LANGUAGE_COOKIE_NAME, language_code)
            return response
        finally:
            if previous_language:
                translation.activate(previous_language)
            else:
                translation.deactivate_all()
            reset_current_user(token)
