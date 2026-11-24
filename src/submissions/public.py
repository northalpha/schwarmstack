"""Öffentliche Endpunkte ohne Cookie und ohne Token: die Community-Zahlen (ADR 0009).

Nicht in `api.py`, denn dort ist alles an die Abgabe aus dem Cookie gebunden.
"""

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .statistics import community_numbers

COMMUNITY_CACHE_KEY = "community_numbers"


def _numbers() -> dict[str, int]:
    seconds = settings.COMMUNITY_CACHE_SECONDS
    if seconds <= 0:
        return community_numbers()
    numbers = cache.get(COMMUNITY_CACHE_KEY)
    if numbers is None:
        numbers = community_numbers()
        cache.set(COMMUNITY_CACHE_KEY, numbers, seconds)
    return numbers


def _allow_origin(response, origin: str | None) -> None:
    """CORS von Hand, ohne weitere Abhängigkeit: `*` für alle, sonst nur gelistete Ursprünge."""
    origins = settings.COMMUNITY_ORIGINS
    if "*" in origins:
        response["Access-Control-Allow-Origin"] = "*"
        return
    if origins:
        response["Vary"] = "Origin"
        if origin in origins:
            response["Access-Control-Allow-Origin"] = origin


@require_GET
def community_numbers_view(request):
    response = JsonResponse(_numbers())
    response["Cache-Control"] = f"public, max-age={max(settings.COMMUNITY_CACHE_SECONDS, 0)}"
    _allow_origin(response, request.headers.get("Origin"))
    return response
