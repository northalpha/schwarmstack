from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
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
        parser.add_argument("--quota-gib", required=True, type=float, help="Quote je Submission")
        parser.add_argument("--global-cap-gib", required=True, type=float, help="Gesamtgrenze")
        parser.add_argument("--grace-hours", type=float, default=6, help="Nachfrist (Standard 6)")
        parser.add_argument(
            "--max-master-mib", type=float, default=500, help="Höchstgröße je Master (Standard 500)"
        )

    def handle(self, *args, **opts):
        campaign = Campaign.current() or Campaign()
        created = campaign.pk is None
        campaign.object_name = opts["object"]
        campaign.starts_at = opts["starts_at"]
        campaign.ends_at = opts["ends_at"]
        campaign.grace_period = timedelta(hours=opts["grace_hours"])
        campaign.quota = int(opts["quota_gib"] * GIB)
        campaign.global_cap = int(opts["global_cap_gib"] * GIB)
        campaign.max_master_size = int(opts["max_master_mib"] * 1024**2)
        try:
            campaign.full_clean()
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages)) from exc
        campaign.save()
        self.stdout.write(f"Aktion {'angelegt' if created else 'geändert'}: {campaign}")
