"""Belichtungsangaben aus den Headern von Mastern lesen, die vor Ticket #50 hochgeladen wurden."""

from django.core.management.base import BaseCommand

from submissions import services
from submissions.models import Master


class Command(BaseCommand):
    help = (
        "Liest die Belichtungsangaben aller angenommenen Master erneut aus ihrem Header. "
        "Werte, die von Hand eingetragen wurden, bleiben unangetastet. Bricht bei einem "
        "Lesefehler ab und lässt sich gefahrlos wiederholen."
    )

    def handle(self, *args, **options):
        count = 0
        for master in Master.objects.filter(state=Master.State.ACCEPTED).iterator():
            services.backfill_exposure(master)
            count += 1
        self.stdout.write(f"Belichtungsangaben für {count} Master aus dem Header gelesen.")
