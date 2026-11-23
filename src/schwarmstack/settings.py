"""Settings, alles aus der Umgebung."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR.parent / "var"))
# SQLite legt die Datenbankdatei an, aber nicht das Verzeichnis darüber.
DATA_DIR.mkdir(parents=True, exist_ok=True)


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str) -> list[str]:
    return [v.strip() for v in os.environ.get(name, "").split(",") if v.strip()]


DEBUG = env_bool("DEBUG")

# Ohne gesetzten Schlüssel startet die App nur im Debug-Modus (lokale Entwicklung, Tests).
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("DJANGO_SECRET_KEY ist nicht gesetzt")
    SECRET_KEY = "nur-fuer-die-entwicklung"  # noqa: S105

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS") or (["localhost", "127.0.0.1"] if DEBUG else [])
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "schwarmstack",
    "storage",
    "submissions",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "schwarmstack.urls"
WSGI_APPLICATION = "schwarmstack.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ]
        },
    }
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "db.sqlite3",
        "OPTIONS": {
            "transaction_mode": "IMMEDIATE",
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
        },
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "de"
TIME_ZONE = "Europe/Berlin"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = DATA_DIR / "static"

# Zugang zur Abgabe nur über ein signiertes Cookie (ADR 0002).
SUBMISSION_COOKIE_SECURE = env_bool("SUBMISSION_COOKIE_SECURE", not DEBUG)
# Version des Hinweistextes, auf den sich eine Einwilligung bezieht.
CONSENT_TEXT_VERSION = os.environ.get("CONSENT_TEXT_VERSION", "2026-11")

# Speicher für Master (ADR 0005): "local" (lokale Platte) oder später "s3".
STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "local")
STORAGE_LOCAL_DIR = Path(os.environ.get("STORAGE_LOCAL_DIR", DATA_DIR / "storage"))
# S3 (nur bei STORAGE_BACKEND=s3). Zugangsdaten kommen aus der Umgebung, nie aus dem Repo.
S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL", "")
S3_BUCKET = os.environ.get("S3_BUCKET", "")
S3_REGION = os.environ.get("S3_REGION", "")
S3_ACCESS_KEY_ID = os.environ.get("S3_ACCESS_KEY_ID", "")
S3_SECRET_ACCESS_KEY = os.environ.get("S3_SECRET_ACCESS_KEY", "")
# "virtual" (Bucket im Hostnamen, z. B. Hetzner) oder "path" (Bucket im Pfad, z. B. Garage lokal)
S3_ADDRESSING_STYLE = os.environ.get("S3_ADDRESSING_STYLE", "virtual")
if STORAGE_BACKEND == "s3" and not S3_BUCKET:
    raise RuntimeError("S3_BUCKET ist nicht gesetzt")
# Gültigkeit signierter Links für einzelne S3-Anfragen.
UPLOAD_LINK_SECONDS = int(os.environ.get("UPLOAD_LINK_SECONDS", 900))

# TLS terminiert vor der App (Caddy); Caddy setzt X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True
SECURE_HSTS_SECONDS = int(os.environ.get("HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_SSL_REDIRECT = False  # Weiterleitung macht der Proxy
SILENCED_SYSTEM_CHECKS = ["security.W008"] + (["security.W004"] if SECURE_HSTS_SECONDS == 0 else [])

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
}
