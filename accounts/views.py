from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import check_for_language
from django.views.decorators.http import require_POST

from core.i18n import localize_url


@require_POST
@login_required
def switch_language(request):
    language = request.POST.get("language", "").strip()
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or reverse("dashboard")
    available_languages = {code for code, _ in settings.LANGUAGES}

    if language in available_languages and check_for_language(language):
        request.user.preferred_language = language
        request.user.save(update_fields=["preferred_language"])
        request.LANGUAGE_CODE = language
        translated_next_url = localize_url(next_url, language) or next_url
        response = HttpResponseRedirect(translated_next_url)
        response.set_cookie(settings.LANGUAGE_COOKIE_NAME, language)
        return response

    return HttpResponseRedirect(next_url)
