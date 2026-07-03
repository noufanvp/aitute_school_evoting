import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file for local development.
# On Render, this is a no-op — Render injects env vars directly into the
# process environment; no .env file is present on the build container.
load_dotenv(BASE_DIR / ".env")

# ---------------------------------------------------------------------------
# Security — reads Render-injected env vars with safe dev fallbacks
# ---------------------------------------------------------------------------

# Render injects SECRET_KEY via render.yaml generateValue.
# Local .env files use DJANGO_SECRET_KEY (legacy name).
# Priority: SECRET_KEY → DJANGO_SECRET_KEY → dev placeholder (DEBUG only).
DEBUG = os.environ.get("DEBUG", "False") == "True"

_dev_placeholder = "dev-insecure-placeholder-do-not-use-in-production" if DEBUG else None
SECRET_KEY = (
    os.environ.get("SECRET_KEY")
    or os.environ.get("DJANGO_SECRET_KEY")
    or _dev_placeholder
)
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY (or DJANGO_SECRET_KEY) environment variable is not set. "
        "Add SECRET_KEY to your Render service environment variables."
    )

# ---------------------------------------------------------------------------
# Hosts — always allows localhost + any Render subdomain automatically
# ---------------------------------------------------------------------------

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# Render injects RENDER_EXTERNAL_HOSTNAME (e.g. school-evoting.onrender.com).
# Appending it covers the exact service hostname without wildcards.
_render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if _render_host:
    ALLOWED_HOSTS.append(_render_host)

# Allow any extra hosts supplied via the legacy DJANGO_ALLOWED_HOSTS var
# (used in local .env / VPS deploys).
_extra_hosts = os.environ.get("DJANGO_ALLOWED_HOSTS", "")
ALLOWED_HOSTS += [h.strip() for h in _extra_hosts.split(",") if h.strip()]

# ---------------------------------------------------------------------------
# CSRF — auto-builds the https Render origin; also reads legacy var
# ---------------------------------------------------------------------------

CSRF_TRUSTED_ORIGINS = []
if _render_host:
    CSRF_TRUSTED_ORIGINS.append(f"https://{_render_host}")

_extra_origins = os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS += [o.strip() for o in _extra_origins.split(",") if o.strip()]

# ---------------------------------------------------------------------------
# Installed apps
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "rest_framework",
    "cloudinary_storage",  # Must come before django.contrib.staticfiles
    "cloudinary",
    "voting",
]

# ---------------------------------------------------------------------------
# Middleware — WhiteNoise must sit directly below SecurityMiddleware
# ---------------------------------------------------------------------------

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",          # ← static files (Render)
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
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
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Database — dj_database_url.config() ingests DATABASE_URL automatically.
# Render injects DATABASE_URL via fromDatabase in render.yaml.
# Falls back to local SQLite for development.
# ---------------------------------------------------------------------------

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# ---------------------------------------------------------------------------
# Auth password validators
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "Asia/Kolkata")
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files — STORAGES dict (Django 4.2+ / 5.x canonical API)
# WhiteNoise CompressedManifestStaticFilesStorage hashes filenames and
# serves brotli/gzip compressed assets directly from Gunicorn on Render.
# ---------------------------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_DIRS = [BASE_DIR / "voting" / "static"]

# ---------------------------------------------------------------------------
# Cloudinary — cloud media storage
# Credentials are injected via environment variables (set on Render dashboard
# and in local .env). When CLOUDINARY_URL is not set or is invalid, the app
# falls back to local FileSystemStorage automatically without crashing.
# ---------------------------------------------------------------------------

_raw_cloudinary_url = os.environ.get("CLOUDINARY_URL", "")

# Only activate Cloudinary if the URL is a real value (starts with cloudinary://)
# This prevents crashes if the env var is set to a placeholder or empty string.
_use_cloudinary = _raw_cloudinary_url.startswith("cloudinary://")

if _use_cloudinary:
    try:
        import cloudinary
        cloudinary.config(cloudinary_url=_raw_cloudinary_url, secure=True)
        CLOUDINARY_URL = _raw_cloudinary_url
    except Exception as e:
        import warnings
        warnings.warn(f"Cloudinary config failed ({e}). Falling back to local storage.")
        _use_cloudinary = False
else:
    if _raw_cloudinary_url:
        import warnings
        warnings.warn(
            f"CLOUDINARY_URL does not start with 'cloudinary://' — value looks like a "
            f"placeholder. Falling back to local file storage."
        )

STORAGES = {
    "default": {
        # Use Cloudinary when CLOUDINARY_URL is valid, otherwise local filesystem
        "BACKEND": (
            "cloudinary_storage.storage.MediaCloudinaryStorage"
            if _use_cloudinary
            else "django.core.files.storage.FileSystemStorage"
        ),
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------------------------------------------------------------------
# URL / auth shortcuts
# ---------------------------------------------------------------------------

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "/invigilator/"
LOGOUT_REDIRECT_URL = "login"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Security headers — Render terminates TLS and forwards X-Forwarded-Proto
# ---------------------------------------------------------------------------

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
X_FRAME_OPTIONS = "DENY"

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

# ---------------------------------------------------------------------------
# Caching Configuration
# ---------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}
