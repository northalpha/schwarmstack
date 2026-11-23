from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError

from submissions.models import Campaign

GIB = 1024**3


def _aware(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise CommandError(f"Ungültiger Zeitpunkt: {value}") from exc
    if parsed.tzinfo is None:
        raise CommandError(f"Zeitpunkt braucht eine Zeitzone, z. B. +01:00: {value}")
    return parsed


class Command(BaseCommand):
    help = "Legt die Aktion an oder ändert sie (genau ein Datensatz)."

    def add_arguments(self, parser):
        parser.add_argument("--object", required=True, help="Objekt, z. B. 'M 101'")
        parser.add_argument("--starts-at", required=True, type=_aware, help="ISO 8601 mit Zone")
        parser.add_argument("--ends-at", required=True, type=_aware, help="ISO 8601 mit Zone")
        parser.add_argument("--quota-gib", required=True, type=float, help="Quote je Abgabe")
        parser.add_argument("--global-cap-gib", required=True, type=float, help="Gesamtgrenze")
        parser.add_argument("--grace-hours", type=float, default=6, help="Nachfrist (Standard 6)")

    def handle(self, *args, **opts):
        if opts["ends_at"] <= opts["starts_at"]:
            raise CommandError("Das Ende der Aktion muss nach dem Beginn liegen.")
        campaign, created = Campaign.objects.update_or_create(
            singleton=True,
            defaults={
                "object_name": opts["object"],
                "starts_at": opts["starts_at"],
                "ends_at": opts["ends_at"],
                "grace_period": timedelta(hours=opts["grace_hours"]),
                "quota": int(opts["quota_gib"] * GIB),
                "global_cap": int(opts["global_cap_gib"] * GIB),
            },
        )
        self.stdout.write(f"Aktion {'angelegt' if created else 'geändert'}: {campaign}")
