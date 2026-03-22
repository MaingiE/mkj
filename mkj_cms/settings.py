"""
MKJ SUPA CUP Competition Management System — Django Settings
"""

import environ
from pathlib import Path
from datetime import timedelta

# ── PATHS ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# ── ENVIRONMENT ────────────────────────────────────────────────────────────────
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

# ── SECURITY ───────────────────────────────────────────────────────────────────
SECRET_KEY = env("SECRET_KEY")
DEBUG      = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

# ── APPS ───────────────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",

    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "crispy_forms",
    "crispy_bootstrap5",

    # MKJ SUPA CUP Apps
    "accounts",
    "competitions",
    "referees.apps.RefereesConfig",
    "teams",
    "matches",
    "admin_dashboard",
    "appeals",
    "news_media",
]

# ── MIDDLEWARE ─────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "accounts.middleware.ForcePasswordChangeMiddleware",
    "admin_dashboard.activity_middleware.ActivityLoggingMiddleware",
]

ROOT_URLCONF   = "mkj_cms.urls"
WSGI_APPLICATION = "mkj_cms.wsgi.application"

# ── TEMPLATES ─────────────────────────────────────────────────────────────────
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.debug",
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

# ── DATABASE ───────────────────────────────────────────────────────────────────
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
    )
}

# ── AUTH ───────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

LOGIN_URL = "web_login"
LOGIN_REDIRECT_URL = "dashboard"

# ── REST FRAMEWORK ─────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# ── JWT ────────────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME":  timedelta(hours=8),
    "REFRESH_TOKEN_LIFETIME":  timedelta(days=7),
    "ROTATE_REFRESH_TOKENS":   True,
    "BLACKLIST_AFTER_ROTATION": True,
    "TOKEN_OBTAIN_SERIALIZER": "accounts.serializers.MKJTokenObtainSerializer",
}

# ── CORS ───────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
])
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# ── SPECTACULAR (API DOCS) ─────────────────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    "TITLE": "MKJ SUPA CUP Competition Management System API",
    "DESCRIPTION": "Governor Mutula Kilonzo Junior Super Cup — Makueni County Sports Competition Management",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "TAGS": [
        {"name": "auth",         "description": "Authentication & user management"},
        {"name": "competitions", "description": "Competition management"},
        {"name": "fixtures",     "description": "Fixture scheduling"},
        {"name": "pools",        "description": "Group/pool management"},
        {"name": "venues",       "description": "Venue management"},
        {"name": "referees",     "description": "Referee management"},
        {"name": "teams",        "description": "Team management"},
        {"name": "players",      "description": "Player management"},
        {"name": "squads",       "description": "Squad submission & approval"},
        {"name": "matches",      "description": "Match reports & results"},
    ],
}

# ── STATIC & MEDIA ─────────────────────────────────────────────────────────────
STATIC_URL  = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL  = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ── CACHE (local memory for dev; switch to Redis in production) ────────────────
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# ── CELERY ─────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL        = env("REDIS_URL", default="redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND    = env("REDIS_URL", default="redis://127.0.0.1:6379/0")
CELERY_ACCEPT_CONTENT    = ["json"]
CELERY_TASK_SERIALIZER   = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE          = "Africa/Nairobi"

# ── EMAIL ──────────────────────────────────────────────────────────────────────
EMAIL_BACKEND    = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST       = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT       = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS    = True
EMAIL_HOST_USER  = env("EMAIL_HOST_USER",     default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = "MKJ SUPA CUP <noreply@mkjsupacup.go.ke>"

# ── LOCALISATION ───────────────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE     = "Africa/Nairobi"
USE_I18N      = True
USE_TZ        = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── SQUAD RULES ────────────────────────────────────────────────────────────────
SQUAD_SUBMISSION_HOURS_BEFORE_KICKOFF = 2
# Default fallbacks — overridden by SPORT_SQUAD_RULES in matches/models.py
SQUAD_MIN_STARTERS = 7      # Minimum starters required
SQUAD_MIN_PLAYERS  = 7      # Absolute minimum players (starters only if no subs)
SQUAD_MAX_PLAYERS  = 23
SQUAD_MAX_STARTERS = 11
SQUAD_MAX_SUBS     = 12

# ── CRISPY FORMS ───────────────────────────────────────────────────────────────
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# ── PLAYER VERIFICATION APIs ──────────────────────────────────────────────────
# FIFA Connect Integration (set API key in .env for production)
FIFA_CONNECT_API_URL = env("FIFA_CONNECT_API_URL", default="https://api.fifaconnect.ke/v1")
FIFA_CONNECT_API_KEY = env("FIFA_CONNECT_API_KEY", default="")
FIFA_CONNECT_ENABLED = env.bool("FIFA_CONNECT_ENABLED", default=True)
FIFA_CONNECT_TIMEOUT = env.int("FIFA_CONNECT_TIMEOUT", default=30)

# Smile Identity — IPRS / Enhanced KYC Verification
# Sign up at smileidentity.com → Dashboard → API Keys
# Use sandbox for testing (SMILE_ENVIRONMENT=sandbox)
SMILE_PARTNER_ID = env("SMILE_PARTNER_ID", default="")
SMILE_API_KEY    = env("SMILE_API_KEY", default="")
SMILE_ENVIRONMENT = env("SMILE_ENVIRONMENT", default="sandbox")  # 'sandbox' or 'production'
SMILE_TIMEOUT    = env.int("SMILE_TIMEOUT", default=30)

IPRS_ENABLED     = env.bool("IPRS_ENABLED", default=True)

# ── PRODUCTION SECURITY HARDENING ──────────────────────────────────────────────
# These settings are enforced when DEBUG=False
if not DEBUG:
    # HTTPS enforcement
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000          # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = "DENY"

# ── LOGGING ────────────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": env("DJANGO_LOG_LEVEL", default="WARNING"),
            "propagate": False,
        },
        "django.security": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}