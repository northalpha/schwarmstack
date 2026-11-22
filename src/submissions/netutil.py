"""Client-Adresse hinter den eigenen Proxys und die davon abgeleiteten Rate-Limits."""

import datetime
import ipaddress

from django.conf import settings
from django.utils import timezone

from .tokens import hash_ip


def client_ip(request) -> str:
    """Adresse des Clients. Hinter Tailscale und Caddy steht sie vor den eigenen Proxys in
    X-Forwarded-For (CLIENT_IP_SKIP Einträge von rechts überspringen). Fehlt sie oder ist sie
    ungültig, gilt REMOTE_ADDR. Ein vom Client mitgeschickter Wert links davon wird ignoriert.
    """
    remote = request.META.get("REMOTE_ADDR", "")
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    skip = settings.CLIENT_IP_SKIP
    if skip > 0 and forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if len(parts) > skip:
            candidate = parts[-skip - 1]
            try:
                return str(ipaddress.ip_address(candidate))
            except ValueError:
                return remote
    return remote


def client_ip_hash(request) -> str:
    return hash_ip(client_ip(request))


def one_hour_ago():
    return timezone.now() - datetime.timedelta(hours=1)
