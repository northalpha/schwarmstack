"""Erreichbarkeit für Deploy-Job und externes Monitoring (ADR 0007).

Antwortet nur mit ok oder nicht ok; Gründe stehen ausschließlich im Log.
"""

import logging

from django.db import connection
from django.http import HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from storage import get_storage

logger = logging.getLogger(__name__)


@never_cache
@require_GET
def healthz(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        get_storage().ensure_reachable()
    except Exception:
        logger.exception("/healthz: nicht ok")
        return HttpResponse("nicht ok", status=503, content_type="text/plain")
    return HttpResponse("ok", content_type="text/plain")
