"""Django settings for Biomedly."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "dev-only-insecure-key-change-me-in-production",
)

DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"

# "*" (default) keeps local dev frictionless. For a real deployment, set
# DJANGO_ALLOWED_HOSTS to a comma-separated list (e.g. "myapp.vercel.app") —
# Django's wildcard is a real Host-header-attack surface in production.
_allowed_hosts = os.getenv("DJANGO_ALLOWED_HOSTS", "*")
ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts.split(",") if h.strip()]

# Vercel (and most PaaS hosts) terminate TLS at a proxy and forward plain
# HTTP internally — without this, Django can't tell the request was HTTPS,
# which breaks secure-cookie and CSRF-origin checks.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
_csrf_hosts = os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "")
if _csrf_hosts:
    CSRF_TRUSTED_ORIGINS = [h.strip() for h in _csrf_hosts.split(",") if h.strip()]
else:
    CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS if h != "*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "cloudinary_storage",
    "cloudinary",
    "accounts",
    "assets",
    "equipment",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
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

# Postgres via DATABASE_URL when set (e.g. Neon); SQLite fallback for dev.
import dj_database_url

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
# Collected here by `collectstatic` (see setup.sh) and served by WhiteNoise
# directly from the WSGI app — works on Vercel's read-only serverless
# filesystem since this only needs write access at BUILD time, not runtime.
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
# Persistent uploads (asset photos, work-order records — NOT the ephemeral
# chat photos, which are never saved) go to Cloudinary when configured, so
# they survive redeploys on hosts with an ephemeral filesystem (Vercel,
# Render/Railway free tiers all wipe local disk between requests/restarts).
if os.getenv("CLOUDINARY_URL"):
    STORAGES["default"] = {"BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage"}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "equipment:home"
LOGOUT_REDIRECT_URL = "accounts:login"

# Max photo upload size (10 MB)
MAX_UPLOAD_SIZE = 10 * 1024 * 1024
