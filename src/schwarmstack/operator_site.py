"""Der Admin für die Betreiber: eigene Site mit Statistik als Startseite und gebremster Anmeldung.

Nur Betreiber haben Konten (per `createsuperuser`), alle mit denselben Rechten. Rollen, Gruppen
und Benutzerverwaltung gibt es hier bewusst nicht.
"""

from django.conf import settings
from django.contrib import admin, messages
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from . import login_limit


class OperatorSite(admin.AdminSite):
    site_header = "Schwarmstack – Betrieb"
    site_title = "Schwarmstack"
    index_title = "Statistik"
    index_template = "admin/statistik.html"

    def index(self, request, extra_context=None):
        """Startseite ist die Statistik, frisch berechnet bei jedem Aufruf."""
        from submissions import export, privacy, statistics
        from submissions.models import Campaign

        missing = privacy.missing_details()
        if missing:
            messages.warning(
                request,
                privacy.missing_message(missing)
                + " Solange sie fehlen, zeigt /datenschutz/ keinen Hinweis. "
                "Siehe docs/betrieb/deployment.md.",
            )
        campaign = Campaign.current()
        context = {
            "statistik": statistics.compute(),
            "campaign": campaign,
            "days_left": export.days_left(campaign) if campaign else None,
        }
        return super().index(request, {**context, **(extra_context or {})})

    @method_decorator(never_cache)
    def login(self, request, extra_context=None):
        if request.method != "POST":
            return super().login(request, extra_context)
        if login_limit.blocked(request):
            # Gesperrt wird vor der Prüfung des Passworts: Auch ein richtiges öffnet jetzt nicht.
            return TemplateResponse(
                request,
                "admin/login_limit.html",
                {
                    **self.each_context(request),
                    "title": "Zu viele Anmeldeversuche",
                    "minutes": -(-settings.LOGIN_ATTEMPTS_WINDOW_SECONDS // 60),
                },
                status=429,
            )
        response = super().login(request, extra_context)
        if request.user.is_authenticated:
            login_limit.succeeded(request)
        else:
            login_limit.failed(request)
        return response


site = OperatorSite(name="operator")
