"""Tokens und Hashes. Tokens werden nie im Klartext gespeichert (HMAC-SHA-256 mit TOKEN_PEPPER)."""

import hashlib
import hmac
import secrets

from django.conf import settings


def new_token() -> str:
    """32 Byte Zufall, URL-sicher (für den Abgabe-Link)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hmac.new(settings.TOKEN_PEPPER.encode(), token.encode(), hashlib.sha256).hexdigest()


def token_matches(token: str, token_hash: str) -> bool:
    return hmac.compare_digest(hash_token(token), token_hash)


def hash_ip(ip: str) -> str:
    """Nur der Hash der IP wird gespeichert (für Rate-Limits), nie die Adresse selbst."""
    return hmac.new(
        settings.TOKEN_PEPPER.encode(), b"ip:" + ip.encode(), hashlib.sha256
    ).hexdigest()
