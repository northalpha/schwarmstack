import random

from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from . import services


@require_GET
@never_cache
def challenge(request):
    """Neue Aufgabe für das ALTCHA-Widget (JSON)."""
    if random.random() < 0.02:  # noqa: S311 - gelegentliches Aufräumen, kein Sicherheitsmerkmal
        services.purge_old()
    return JsonResponse(services.new_challenge())
