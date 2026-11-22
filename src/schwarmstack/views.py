from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@require_GET
def home(request):
    return render(request, "home.html")


@require_GET
@never_cache
def healthz(request):
    """Lebenszeichen für Caddy, Monitoring und Ansible: prüft auch die Datenbank."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:  # noqa: BLE001 - jeder DB-Fehler heißt "nicht gesund"
        return HttpResponse("db error", status=503, content_type="text/plain")
    return JsonResponse({"status": "ok"})
