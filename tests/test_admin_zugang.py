"""Zugang zum Admin: eigener Pfad, nur mit Konto, gebremste Anmeldung (Ticket #29)."""

import pytest
from admin_helper import ADMIN
from django.test import Client

pytestmark = pytest.mark.django_db


def login(client, password, ip="203.0.113.7"):
    return client.post(
        f"{ADMIN}login/",
        {"username": "ada", "password": password, "next": ADMIN},
        REMOTE_ADDR=ip,
    )


def test_admin_liegt_nicht_unter_admin(operator_client):
    assert operator_client.get("/admin/").status_code == 404


def test_ohne_anmeldung_kein_zugang(client):
    response = client.get(ADMIN)
    assert response.status_code == 302
    assert response["Location"].startswith(f"{ADMIN}login/")


def test_betreiber_meldet_sich_an(operator, operator_password):
    client = Client()
    response = login(client, operator_password)
    assert response.status_code == 302
    assert client.get(ADMIN).status_code == 200


def test_wiederholte_fehlversuche_werden_gebremst(operator, operator_password):
    client = Client()
    for _ in range(5):
        assert login(client, "falsch").status_code == 200
    response = login(client, operator_password)  # auch das richtige Passwort hilft jetzt nicht
    assert response.status_code == 429
    assert client.get(ADMIN).status_code == 302


def test_bremse_gilt_je_ip(operator, operator_password):
    for _ in range(5):
        login(Client(), "falsch", ip="203.0.113.7")
    assert login(Client(), operator_password, ip="198.51.100.9").status_code == 302


def test_ip_wird_nur_als_hash_gespeichert(operator):
    from schwarmstack.models import LoginAttempt

    login(Client(), "falsch", ip="203.0.113.7")
    stored = LoginAttempt.objects.get()
    assert "203.0.113.7" not in stored.ip_hash


def test_hinter_dem_proxy_zaehlt_die_ip_aus_x_forwarded_for(operator, operator_password, settings):
    settings.TRUST_X_FORWARDED_FOR = True

    def via_proxy(password, forwarded):
        return Client().post(
            f"{ADMIN}login/",
            {"username": "ada", "password": password, "next": ADMIN},
            REMOTE_ADDR="172.18.0.2",
            HTTP_X_FORWARDED_FOR=forwarded,
        )

    for _ in range(5):
        # Den vorderen Teil kann der Angreifer selbst setzen; zählen darf nur der letzte.
        via_proxy("falsch", f"10.0.0.{_}, 203.0.113.7")
    assert via_proxy(operator_password, "203.0.113.7").status_code == 429
    assert via_proxy(operator_password, "198.51.100.9").status_code == 302


def test_ip_hashes_bleiben_hoechstens_eine_stunde(operator):
    """Der Datenschutzhinweis sagt: IP-Hashes fürs Rate-Limit nur stundenweise (Ticket #34)."""
    from datetime import timedelta

    from django.core.management import call_command
    from django.utils import timezone

    from schwarmstack.models import LoginAttempt

    login(Client(), "falsch")
    old = LoginAttempt.objects.create(ip_hash="b" * 64)
    LoginAttempt.objects.filter(pk=old.pk).update(at=timezone.now() - timedelta(minutes=61))
    call_command("forget_login_attempts")
    assert not LoginAttempt.objects.filter(pk=old.pk).exists()
    assert LoginAttempt.objects.count() == 1  # der frische Fehlversuch bleibt
