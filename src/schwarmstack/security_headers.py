"""Sicherheits-Header auf jeder Antwort: strenge Content-Security-Policy, Clickjacking-Schutz und
Permissions-Policy (Ticket #122).

Eine eigene Middleware statt Caddy: So gelten die Header auch im E2E-Test gegen `live_server`
(dort prüft der echte Browser die Policy mit) und bei jedem Betrieb, auch hinter einem anderen
Proxy. HSTS, `nosniff`, Referrer-Policy und die Cookies setzen weiter Django und die Settings.

Die Policy kennt kein `unsafe-inline`: Skripte und Styles liegen als statische Dateien vor, nie
inline im HTML. Das gilt auch für den Admin der Betreiber.
"""

from urllib.parse import urlsplit

from django.conf import settings

# Nichts davon braucht die App; der Browser soll es auch dann verweigern, wenn sich ein Skript
# einschleicht.
PERMISSIONS_POLICY = (
    "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), "
    "microphone=(), payment=(), usb=(), interest-cohort=()"
)


def s3_origin() -> str | None:
    """Ursprung, zu dem der Browser die Master hochlädt (Uppy -> S3, ADR 0005).

    Bei lokalem Speicher bildet `/_lokal/s3/` das nach (gleicher Ursprung), dann gibt es keinen.
    """
    if settings.STORAGE_BACKEND != "s3":
        return None
    endpoint = urlsplit(settings.S3_ENDPOINT_URL or "")
    if not endpoint.netloc:
        # Kein eigener Endpunkt: AWS selbst, der Bucket steht im Hostnamen.
        return "https://*.amazonaws.com"
    if settings.S3_ADDRESSING_STYLE == "path":
        return f"{endpoint.scheme}://{endpoint.netloc}"
    return f"{endpoint.scheme}://{settings.S3_BUCKET}.{endpoint.netloc}"


def content_security_policy() -> str:
    connect = ["'self'"]
    if origin := s3_origin():
        connect.append(origin)
    return "; ".join(
        [
            "default-src 'self'",
            "script-src 'self'",
            f"connect-src {' '.join(connect)}",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ]
    )


class SecurityHeadersMiddleware:
    """Ganz außen, damit auch Fehlerantworten (400 bei falschem Host, 500) die Header tragen."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # `CSP_REPORT_ONLY` nur zum Einführen oder Zurückstellen im Betrieb: Der Browser meldet
        # Verstöße in der Konsole, blockiert aber nichts.
        name = (
            "Content-Security-Policy-Report-Only"
            if settings.CSP_REPORT_ONLY
            else "Content-Security-Policy"
        )
        response[name] = content_security_policy()
        # Auch dort, wo XFrameOptionsMiddleware nicht mehr dran kommt (400 vor CommonMiddleware).
        response["X-Frame-Options"] = "DENY"
        response["Permissions-Policy"] = PERMISSIONS_POLICY
        return response
