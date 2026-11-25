from django.core.management.base import BaseCommand

from submissions import deletion


class Command(BaseCommand):
    help = (
        "Löscht nach Ablauf der Löschfrist alle Master, Begleitdateien und Angaben (ADR 0008). "
        "Täglich per Cron aufrufen; vorher tut der Befehl nichts, sieben Tage vorher erinnert er."
    )

    def handle(self, *args, **options):
        outcome = deletion.run()
        self.stdout.write(f"Löschfrist: {outcome.value}")
