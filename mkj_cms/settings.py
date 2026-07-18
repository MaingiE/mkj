"""
MKJ SUPA CUP Competition Management System - Django Settings
"""

import environ
import sentry_sdk
from pathlib import Path
from datetime import timedelta

# ── PATHS ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# ── ENVIRONMENT ────────────────────────────────────────────────────────────────
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

# Support .env.test override: set TEST_MODE=1 in your shell to use db_test.sqlite3
# e.g.  $env:TEST_MODE="1"; python manage.py runserver   (PowerShell)
import os as _os
if _os.environ.get("TEST_MODE") == "1":
    # Use a dedicated test database so main data is never touched
    _os.environ.setdefault("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db_test.sqlite3'}")
    _os.environ.setdefault("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")

# ── SECURITY ───────────────────────────────────────────────────────────────────
SECRET_KEY = "django-insecure-local-dev-only-replace-this-in-production"
DEBUG      = env.bool("DEBUG", default=True)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=(
    ["127.0.0.1", "localhost"] if DEBUG else [
        "mkjsupacup.com",
        "www.mkjsupacup.com",
        ".railway.app",
        "healthcheck.railway.app",
    ]
))
# Always allow Railway's internal healthcheck host regardless of env var value
if "healthcheck.railway.app" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("healthcheck.railway.app")

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
    "cloudinary_storage",
    "cloudinary",

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
    "accounts.middleware.BotBlockerMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "accounts.middleware.AutoLogoutMiddleware",
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
    "default": {
        **env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        "CONN_MAX_AGE": env.int("DB_CONN_MAX_AGE", default=0 if DEBUG else 300),
        "CONN_HEALTH_CHECKS": True,
    }
}

# ── AUTH ───────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"

# Use Argon2 (OWASP-recommended, memory-hard) as the primary hasher.
# Existing PBKDF2 hashes are auto-verified and upgraded to Argon2 on next login.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {"NAME": "accounts.validators.StrongPasswordValidator"},
]

AUTHENTICATION_BACKENDS = [
    "accounts.backends.EmailBackend",
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

CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[
    "https://mkjsupacup.com",
    "https://www.mkjsupacup.com",
])

# ── SPECTACULAR (API DOCS) ─────────────────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    "TITLE": "MKJ SUPA CUP Competition Management System API",
    "DESCRIPTION": "Governor Mutula Kilonzo Junior Supa Cup - Makueni County Sports Competition Management",
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

# ── AWS S3 (media storage in production) ──────────────────────────────────────
AWS_ACCESS_KEY_ID       = env("AWS_ACCESS_KEY_ID",       default="")
AWS_SECRET_ACCESS_KEY   = env("AWS_SECRET_ACCESS_KEY",   default="")
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="")
AWS_S3_REGION_NAME      = env("AWS_S3_REGION_NAME",      default="af-south-1")
AWS_S3_CUSTOM_DOMAIN    = env("AWS_S3_CUSTOM_DOMAIN",    default="")
AWS_S3_FILE_OVERWRITE   = False
AWS_DEFAULT_ACL         = None
AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}

_use_s3 = not DEBUG and bool(AWS_ACCESS_KEY_ID and AWS_STORAGE_BUCKET_NAME)
_cloudinary_url = env("CLOUDINARY_URL", default="")
_use_cloudinary = not DEBUG and bool(_cloudinary_url)

if _use_cloudinary:
    import cloudinary
    from urllib.parse import urlparse
    _cld = urlparse(_cloudinary_url)
    _cld_cloud  = _cld.hostname or env("CLOUDINARY_CLOUD_NAME", default="")
    _cld_key    = _cld.username or env("CLOUDINARY_API_KEY", default="")
    _cld_secret = _cld.password or env("CLOUDINARY_API_SECRET", default="")

    cloudinary.config(
        cloud_name=_cld_cloud, api_key=_cld_key,
        api_secret=_cld_secret, secure=True,
    )
    CLOUDINARY_STORAGE = {
        "CLOUD_NAME": _cld_cloud,
        "API_KEY":    _cld_key,
        "API_SECRET": _cld_secret,
    }
    STORAGES["default"] = {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    }
    MEDIA_URL = "/media/"
elif _use_s3:
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "bucket_name": AWS_STORAGE_BUCKET_NAME,
            "region_name": AWS_S3_REGION_NAME,
            "custom_domain": AWS_S3_CUSTOM_DOMAIN or None,
            "location": "media",
        },
    }

# ── CACHE ──────────────────────────────────────────────────────────────────────
if DEBUG:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": env("REDIS_URL", default="redis://127.0.0.1:6379/1"),
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "SOCKET_CONNECT_TIMEOUT": 5,
                "SOCKET_TIMEOUT": 5,
                "RETRY_ON_TIMEOUT": True,
            },
        }
    }

# ── SESSIONS ───────────────────────────────────────────────────────────────────
if DEBUG:
    SESSION_ENGINE = "django.contrib.sessions.backends.db"
else:
    SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
    SESSION_CACHE_ALIAS = "default"

SESSION_COOKIE_AGE = 60 * 60 * 2
SESSION_SAVE_EVERY_REQUEST = False
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
AUTO_LOGOUT_IDLE_MINUTES = 30

# ── CELERY ─────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL        = env("REDIS_URL", default="redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND    = env("REDIS_URL", default="redis://127.0.0.1:6379/0")
CELERY_ACCEPT_CONTENT    = ["json"]
CELERY_TASK_SERIALIZER   = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE          = "Africa/Nairobi"

# ── EMAIL ──────────────────────────────────────────────────────────────────────
_email_host_user = env("EMAIL_HOST_USER", default="")
EMAIL_BACKEND    = env(
    "EMAIL_BACKEND",
    default=(
        "accounts.brevo_backend.BrevoEmailBackend"
        if _email_host_user
        else (
            "django.core.mail.backends.console.EmailBackend"
            if DEBUG
            else "accounts.brevo_backend.BrevoEmailBackend"
        )
    ),
)
EMAIL_HOST       = env("EMAIL_HOST",     default="mail.privateemail.com")
EMAIL_PORT       = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS    = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL    = env.bool("EMAIL_USE_SSL", default=False)
EMAIL_TIMEOUT    = env.int("EMAIL_TIMEOUT", default=15)
EMAIL_HOST_USER  = _email_host_user
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL  = env("DEFAULT_FROM_EMAIL", default="MKJ SUPA CUP <info@mkjsupacup.com>")
BREVO_API_KEY       = env("BREVO_API_KEY", default="")
SITE_URL = env("SITE_URL", default="https://mkjsupacup.com")

# ── WHATSAPP (Brevo WhatsApp API) ─────────────────────────────────────────────
# Set BREVO_WHATSAPP_SENDER to your WhatsApp Business number (+254XXXXXXXXX)
# Template IDs from your Brevo account (WhatsApp → Templates):
BREVO_WHATSAPP_SENDER                    = env("BREVO_WHATSAPP_SENDER", default="")
BREVO_WHATSAPP_TEMPLATE_CREDENTIALS      = env("BREVO_WHATSAPP_TEMPLATE_CREDENTIALS", default="")
BREVO_WHATSAPP_TEMPLATE_PASSWORD_RESET   = env("BREVO_WHATSAPP_TEMPLATE_PASSWORD_RESET", default="")
BREVO_WHATSAPP_TEMPLATE_DEADLINE         = env("BREVO_WHATSAPP_TEMPLATE_DEADLINE", default="")
BREVO_WHATSAPP_TEMPLATE_TRANSFER         = env("BREVO_WHATSAPP_TEMPLATE_TRANSFER", default="")
BREVO_WHATSAPP_TEMPLATE_LONGLIST_STATUS  = env("BREVO_WHATSAPP_TEMPLATE_LONGLIST_STATUS", default="")
BREVO_WHATSAPP_TEMPLATE_SQUAD_RESULT     = env("BREVO_WHATSAPP_TEMPLATE_SQUAD_RESULT", default="")

# ── DUAL EMAIL SENDERS ────────────────────────────────────────────────────────
# admin@mkjsupacup.com    — general admin, system, and leadership notifications
# ligimashinani@mkjsupacup.com — Ligi Mashinani team manager notifications
DEFAULT_FROM_EMAIL      = env("DEFAULT_FROM_EMAIL",      default="MKJ SUPA CUP <admin@mkjsupacup.com>")
LIGI_FROM_EMAIL         = env("LIGI_FROM_EMAIL",         default="Ligi Mashinani <ligimashinani@mkjsupacup.com>")

# ── SEO CONFIGURATION ──────────────────────────────────────────────────────────
SITE_NAME = "MKJ SUPA CUP"
SITE_DESCRIPTION = (
    "Governor Mutula Kilonzo Junior Supa Cup - Official youth sports championship "
    "for Makueni County, Kenya. Football, Volleyball, Basketball and Handball."
)
SEO_KEYWORDS = [
    "MKJ SUPA CUP",
    "Mutula Kilonzo Junior",
    "Supa Cup",
    "Makueni County sports",
    "youth championship Kenya",
    "Makueni football",
    "Makueni volleyball",
    "Makueni basketball",
    "Makueni handball",
    "Kenya youth sports",
    "sub-county sports",
    "MKJ TINA",
    "Governor Mutula Kilonzo Junior",
    "Wote sports",
    "Makueni competition",
]

# ── IMAP (inbound mail fetch) ──────────────────────────────────────────────────
IMAP_HOST     = env("IMAP_HOST",     default="mail.privateemail.com")
IMAP_PORT     = env.int("IMAP_PORT",  default=993)
IMAP_USE_SSL  = env.bool("IMAP_USE_SSL", default=True)
IMAP_USER     = env("IMAP_USER",     default="info@mkjsupacup.com")
IMAP_PASSWORD = env("IMAP_PASSWORD", default="")

# ── LOCALISATION ───────────────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE     = "Africa/Nairobi"
USE_I18N      = True
USE_TZ        = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── SQUAD RULES ────────────────────────────────────────────────────────────────
SQUAD_SUBMISSION_HOURS_BEFORE_KICKOFF = 2
SQUAD_MIN_STARTERS = 7
SQUAD_MIN_PLAYERS  = 7
SQUAD_MAX_PLAYERS  = 23
SQUAD_MAX_STARTERS = 11
SQUAD_MAX_SUBS     = 12

# ── CRISPY FORMS ───────────────────────────────────────────────────────────────
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# ── PLAYER VERIFICATION APIs ──────────────────────────────────────────────────
FIFA_CONNECT_API_URL = env("FIFA_CONNECT_API_URL", default="https://api.fifaconnect.ke/v1")
FIFA_CONNECT_API_KEY = env("FIFA_CONNECT_API_KEY", default="")
FIFA_CONNECT_ENABLED = env.bool("FIFA_CONNECT_ENABLED", default=True)
FIFA_CONNECT_TIMEOUT = env.int("FIFA_CONNECT_TIMEOUT", default=30)

SMILE_PARTNER_ID  = env("SMILE_PARTNER_ID", default="")
SMILE_API_KEY     = env("SMILE_API_KEY", default="")
SMILE_ENVIRONMENT = env("SMILE_ENVIRONMENT", default="sandbox")
SMILE_TIMEOUT     = env.int("SMILE_TIMEOUT", default=30)

IPRS_ENABLED = env.bool("IPRS_ENABLED", default=True)

# ── SERVER ERROR EMAIL ─────────────────────────────────────────────────────────
ADMINS = [tuple(a.split(":")) for a in env.list("ADMINS", default=[])]
SERVER_EMAIL = env("SERVER_EMAIL", default="info@mkjsupacup.com")

# ── SENTRY ERROR TRACKING ──────────────────────────────────────────────────────
SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
        send_default_pii=False,
        environment=env("SENTRY_ENVIRONMENT", default="production"),
    )

# ── PRODUCTION SECURITY HARDENING ──────────────────────────────────────────────
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
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
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "mail_admins": {
            "level": "ERROR",
            "filters": ["require_debug_false"],
            "class": "django.utils.log.AdminEmailHandler",
            "include_html": True,
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
        "django.request": {
            "handlers": ["console", "mail_admins"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}