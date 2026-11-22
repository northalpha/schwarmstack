"""Zweiten Faktor (TOTP) für einen Admin-Benutzer einrichten.

Ohne bestätigtes Gerät kommt niemand in den Admin. Der Befehl legt das Gerät an, zeigt den
QR-Code im Terminal und erzeugt einmalig Wiederherstellungscodes:
    sudo schwarmstack-manage otp_setup <benutzer>
"""

import sys

import qrcode
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

RECOVERY_CODES = 8


class Command(BaseCommand):
    help = "Richtet TOTP (Authenticator-App) und Wiederherstellungscodes für einen Benutzer ein."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Vorhandene Geräte löschen und neu einrichten (Gerät verloren).",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            user = User.objects.get(**{User.USERNAME_FIELD: options["username"]})
        except User.DoesNotExist as exc:
            raise CommandError(f"Benutzer {options['username']!r} gibt es nicht.") from exc
        if not user.is_staff:
            raise CommandError("Der Benutzer ist kein Admin (is_staff).")

        existing = TOTPDevice.objects.filter(user=user)
        if existing.exists() and not options["reset"]:
            raise CommandError("Es gibt schon ein Gerät. Zum Ersetzen --reset angeben.")
        if options["reset"]:
            TOTPDevice.objects.filter(user=user).delete()
            StaticDevice.objects.filter(user=user).delete()

        device = TOTPDevice.objects.create(user=user, name="authenticator", confirmed=True)
        qr = qrcode.QRCode(border=1)
        qr.add_data(device.config_url)
        qr.make()
        self.stdout.write("QR-Code in der Authenticator-App scannen:\n")
        qr.print_ascii(out=sys.stdout, invert=True)
        self.stdout.write(f"\nOder von Hand eintragen: {device.config_url}\n")

        recovery = StaticDevice.objects.create(user=user, name="wiederherstellung", confirmed=True)
        self.stdout.write("\nWiederherstellungscodes (jeder gilt einmal, jetzt sicher ablegen):")
        for _ in range(RECOVERY_CODES):
            token = StaticToken.random_token()
            recovery.token_set.create(token=token)
            self.stdout.write(f"  {token}")
