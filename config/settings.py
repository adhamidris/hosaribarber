import os
from pathlib import Path
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file(env_path: Path):
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ[key] = value


_load_env_file(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "replace-this-in-production")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [host for host in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",") if host]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "accounts",
    "clients",
    "services",
    "appointments",
    "auditlog",
    "ai_playground",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.UserPreferredLanguageMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en"
LANGUAGES = [
    ("en", _("English")),
    ("ar", _("Arabic")),
]
LOCALE_PATHS = [BASE_DIR / "locale"]

TIME_ZONE = "Africa/Cairo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

DEFAULT_CURRENCY = "EGP"
SHOP_TIMEZONE = "Africa/Cairo"
LANGUAGE_COOKIE_NAME = "barber_crm_language"

AI_PLAYGROUND_SESSION_DURATION_MINUTES = int(
    os.getenv("AI_PLAYGROUND_SESSION_DURATION_MINUTES", "30")
)
AI_PLAYGROUND_MAX_IMAGE_SIZE_BYTES = int(
    os.getenv("AI_PLAYGROUND_MAX_IMAGE_SIZE_BYTES", str(6 * 1024 * 1024))
)
AI_PLAYGROUND_PROVIDER = os.getenv("AI_PLAYGROUND_PROVIDER", "stub").strip().lower()
AI_PLAYGROUND_PROVIDER_TIMEOUT_SECONDS = int(
    os.getenv("AI_PLAYGROUND_PROVIDER_TIMEOUT_SECONDS", "120")
)
AI_PLAYGROUND_SESSION_GENERATION_LIMIT = int(
    os.getenv("AI_PLAYGROUND_SESSION_GENERATION_LIMIT", "5")
)
AI_PLAYGROUND_MIN_GENERATE_INTERVAL_SECONDS = int(
    os.getenv("AI_PLAYGROUND_MIN_GENERATE_INTERVAL_SECONDS", "10")
)
AI_PLAYGROUND_START_MAX_PER_IP_PER_HOUR = int(
    os.getenv("AI_PLAYGROUND_START_MAX_PER_IP_PER_HOUR", "120")
)
AI_PLAYGROUND_GENERATE_MAX_PER_IP_PER_HOUR = int(
    os.getenv("AI_PLAYGROUND_GENERATE_MAX_PER_IP_PER_HOUR", "60")
)
AI_PLAYGROUND_DATA_RETENTION_HOURS = int(
    os.getenv("AI_PLAYGROUND_DATA_RETENTION_HOURS", "24")
)
_ai_playground_one_style_raw = os.getenv("AI_PLAYGROUND_ONE_STYLE_PER_SESSION", "1")
AI_PLAYGROUND_ONE_STYLE_PER_SESSION = _ai_playground_one_style_raw == "1"
AI_PLAYGROUND_SESSION_COOKIE_NAME = os.getenv(
    "AI_PLAYGROUND_SESSION_COOKIE_NAME",
    "ai_playground_session",
)
_ai_playground_cookie_secure_raw = os.getenv("AI_PLAYGROUND_SESSION_COOKIE_SECURE")
if _ai_playground_cookie_secure_raw is None:
    AI_PLAYGROUND_SESSION_COOKIE_SECURE = not DEBUG
else:
    AI_PLAYGROUND_SESSION_COOKIE_SECURE = _ai_playground_cookie_secure_raw == "1"

AI_PLAYGROUND_NANOBANANA_API_KEY = os.getenv("AI_PLAYGROUND_NANOBANANA_API_KEY", "")
AI_PLAYGROUND_NANOBANANA_MODEL = os.getenv(
    "AI_PLAYGROUND_NANOBANANA_MODEL",
    "gemini-2.5-flash-image",
)
AI_PLAYGROUND_NANOBANANA_ENDPOINT = os.getenv("AI_PLAYGROUND_NANOBANANA_ENDPOINT", "")
AI_PLAYGROUND_NANOBANANA_INPUT_COST_PER_1M_TOKENS = os.getenv(
    "AI_PLAYGROUND_NANOBANANA_INPUT_COST_PER_1M_TOKENS",
    "0",
)
AI_PLAYGROUND_NANOBANANA_OUTPUT_COST_PER_1M_TOKENS = os.getenv(
    "AI_PLAYGROUND_NANOBANANA_OUTPUT_COST_PER_1M_TOKENS",
    "0",
)

AI_PLAYGROUND_GROK_API_KEY = os.getenv("AI_PLAYGROUND_GROK_API_KEY", "")
AI_PLAYGROUND_GROK_MODEL = os.getenv("AI_PLAYGROUND_GROK_MODEL", "grok-2-image")
AI_PLAYGROUND_GROK_IMAGES_ENDPOINT = os.getenv(
    "AI_PLAYGROUND_GROK_IMAGES_ENDPOINT",
    "https://api.x.ai/v1/images/edits",
)
AI_PLAYGROUND_GROK_IMAGE_FORMAT = os.getenv("AI_PLAYGROUND_GROK_IMAGE_FORMAT", "base64")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "ai_playground.nanobanana.usage": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
