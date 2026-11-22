from django.conf import settings
from django.shortcuts import render
from django.views.decorators.http import require_GET


def _context() -> dict:
    return {
        "operator_name": settings.OPERATOR_NAME,
        "operator_address": settings.OPERATOR_ADDRESS,
        "operator_email": settings.OPERATOR_EMAIL,
        "retention_months": settings.RETENTION_MONTHS,
        "extra_processors": settings.PRIVACY_EXTRA_PROCESSORS,
        "project_use_text": settings.PROJECT_USE_TEXT,
        "version": settings.CONSENT_TEXT_VERSION,
    }


@require_GET
def datenschutz(request):
    return render(request, "legal/datenschutz.html", _context())


@require_GET
def impressum(request):
    return render(request, "legal/impressum.html", _context())
