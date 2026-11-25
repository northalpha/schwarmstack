from django.core.management.base import BaseCommand

from schwarmstack import login_limit


class Command(BaseCommand):
    help = "Löscht IP-Hashes fehlgeschlagener Anmeldungen, die älter als eine Stunde sind."

    def handle(self, *args, **options):
        self.stdout.write(f"{login_limit.forget_old()} alte Fehlversuche gelöscht")
