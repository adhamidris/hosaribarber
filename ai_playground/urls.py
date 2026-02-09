from django.urls import path

from .views import (
    generate_preview,
    playground_home,
    start_session,
    styles_api,
    upload_selfie,
)

urlpatterns = [
    path("", playground_home, name="ai-playground-home"),
    path("start/", start_session, name="ai-playground-start"),
    path("api/styles/", styles_api, name="ai-playground-styles"),
    path("api/selfie/", upload_selfie, name="ai-playground-selfie-upload"),
    path("api/generate/", generate_preview, name="ai-playground-generate"),
]
