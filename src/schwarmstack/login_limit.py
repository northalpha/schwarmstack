"""Rate-Limit für die Anmeldung am Admin, je IP, gespeichert nur als Hash (ADR 0002)."""

import hashlib
import hmac
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import LoginAttempt


def client_ip(request) -> str:
    if settings.TRUST_X_FORWARDED_FOR:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded.strip():
            return forwarded.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "")


def _hash(request) -> str:
    key = settings.SECRET_KEY.encode()
    return hmac.new(key, client_ip(request).encode(), hashlib.sha256).hexdigest()


def _recent():
    since = timezone.now() - timedelta(seconds=settings.LOGIN_ATTEMPTS_WINDOW_SECONDS)
    LoginAttempt.objects.filter(at__lt=since).delete()
    return LoginAttempt.objects.all()


def blocked(request) -> bool:
    return _recent().filter(ip_hash=_hash(request)).count() >= settings.LOGIN_ATTEMPTS_MAX


def failed(request) -> None:
    LoginAttempt.objects.create(ip_hash=_hash(request))


def succeeded(request) -> None:
    LoginAttempt.objects.filter(ip_hash=_hash(request)).delete()
