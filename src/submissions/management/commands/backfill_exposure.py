"""Belichtungsangaben für Master nachtragen, die vor Ticket #50 hochgeladen wurden."""

from django.core.management.base import BaseCommand

from submissions import services
from submissions.models import Master


class Command(BaseCommand):
    help = (
        "Liest die Header aller angenommenen Master erneut und trägt die Belichtungsangaben "
        "nach. Werte, die von Hand eingetragen wurden, bleiben unangetastet. Lässt sich "
        "gefahrlos wiederholen."
    )

    def handle(self, *args, **options):
        count = 0
        for master in Master.objects.filter(state=Master.State.ACCEPTED).iterator():
            services.backfill_exposure(master)
            count += 1
        self.stdout.write(f"Belichtungsangaben für {count} Master nachgetragen.")
