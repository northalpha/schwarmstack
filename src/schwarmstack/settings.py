"""Settings, alles aus der Umgebung (/etc/schwarmstack/schwarmstack.env)."""

import hashlib
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR.parent / "var"))


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str) -> list[str]:
    return [v.strip() for v in os.environ.get(name, "").split(",") if v.strip()]


DEBUG = env_bool("DEBUG")

# Ohne gesetzten Schlüssel startet die App nur im Debug-Modus (lokale Entwicklung/Tests).
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("DJANGO_SECRET_KEY ist nicht gesetzt")
    SECRET_KEY = "nur-fuer-die-entwicklung"  # noqa: S105

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS") or (["localhost", "127.0.0.1"] if DEBUG else [])
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "schwarmstack.apps.OTPAdminConfig",  # ersetzt django.contrib.admin (mit 2FA)
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
    "submissions",
    "uploads",
    "packing",
    "altcha_gate",
    "entry",
    "legal",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "schwarmstack.urls"
WSGI_APPLICATION = "schwarmstack.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "schwarmstack" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "schwarmstack.context.site",
            ]
        },
    }
]

# Pfad des Django-Admins (die Caddyfile sperrt ihn auf dem öffentlichen Listener)
ADMIN_PATH = os.environ.get("ADMIN_PATH", "admin").strip("/")

# Tokens (Abgabe-Link, Upload-Token) werden nur als HMAC-SHA-256 mit diesem Pfeffer gespeichert.
TOKEN_PEPPER = os.environ.get("TOKEN_PEPPER", "")
if not TOKEN_PEPPER:
    if not DEBUG:
        raise RuntimeError("TOKEN_PEPPER ist nicht gesetzt")
    TOKEN_PEPPER = "nur-fuer-die-entwicklung"  # noqa: S105

# Vorgaben für neue Events (Produktion 1,5 GiB / 400 GiB, Staging 1 GiB / 4 GiB aus der Rolle)
DEFAULT_QUOTA_BYTES = int(os.environ.get("DEFAULT_QUOTA_BYTES", 1610612736))
DEFAULT_GLOBAL_CAP_BYTES = int(os.environ.get("DEFAULT_GLOBAL_CAP_BYTES", 429496729600))

OTP_TOTP_ISSUER = "Schwarmstack"

# --- Einstieg über die Projektwebsite (Referer-Tor, Entry-Ticket) und Abgabe ---------------
ENTRY_TICKET_COOKIE = "entry_ticket"
ENTRY_TICKET_MAX_AGE = 3600  # 60 Minuten
SUBMISSION_COOKIE = "abgabe_token"
SUBMISSION_COOKIE_MAX_AGE = 60 * 60 * 24 * 180
CONSENT_TEXT_VERSION = "2026-11"
# Rate-Limits je gehashter IP und Stunde (Datenbank, kein Redis)
RATE_ENTRY_PER_HOUR = int(os.environ.get("RATE_ENTRY_PER_HOUR", 20))
RATE_SUBMISSIONS_PER_HOUR = int(os.environ.get("RATE_SUBMISSIONS_PER_HOUR", 5))
# Wie viele Einträge am Ende von X-Forwarded-For stammen von eigenen Proxys (Caddy: 1 hinter
# Tailscale, sonst 0). Der Wert davor ist die Client-Adresse; ohne Eintrag gilt REMOTE_ADDR.
CLIENT_IP_SKIP = int(os.environ.get("CLIENT_IP_SKIP", 0))

# --- Betreiberdaten, Datenschutz ---------------------------------------------------------------
TEST_SYSTEM = env_bool("TEST_SYSTEM")
OPERATOR_NAME = os.environ.get("OPERATOR_NAME", "")
OPERATOR_ADDRESS = os.environ.get("OPERATOR_ADDRESS", "")
OPERATOR_EMAIL = os.environ.get("OPERATOR_EMAIL", "")
RETENTION_MONTHS = int(os.environ.get("RETENTION_MONTHS", 6))
PROJECT_USE_TEXT = os.environ.get("PROJECT_USE_TEXT", "")
PRIVACY_EXTRA_PROCESSORS = [
    p.strip() for p in os.environ.get("PRIVACY_EXTRA_PROCESSORS", "").split("|") if p.strip()
]

# ALTCHA (optional pro Event): Proof-of-Work-Prüfung ohne Drittanbieter
ALTCHA_ALGORITHM = "PBKDF2/SHA-256"
ALTCHA_COST = int(os.environ.get("ALTCHA_COST", 5000))
ALTCHA_EXPIRY_SECONDS = 600
ALTCHA_HMAC_SECRET = (
    os.environ.get("ALTCHA_HMAC_SECRET")
    or hashlib.sha256(b"altcha:" + SECRET_KEY.encode()).hexdigest()
)

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
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
STATICFILES_DIRS = [BASE_DIR / "schwarmstack" / "static"]
STATIC_ROOT = DATA_DIR / "static"

# TLS terminiert vor der App (Caddy bzw. Tailscale); Caddy setzt X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True
# HSTS nur in Produktion (Caddy-TLS), auf Staging aus.
SECURE_HSTS_SECONDS = int(os.environ.get("HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_SSL_REDIRECT = False  # Weiterleitung macht der Proxy
# W008: Weiterleitung auf HTTPS übernimmt der Proxy. W004: HSTS ist auf Staging bewusst aus.
SILENCED_SYSTEM_CHECKS = ["security.W008"] + (["security.W004"] if SECURE_HSTS_SECONDS == 0 else [])

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
}
