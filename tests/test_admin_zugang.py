"""Zugang zum Admin: eigener Pfad, nur mit Konto, gebremste Anmeldung (Ticket #29)."""

import pytest
from admin_helper import ADMIN, PASSWORD, operator, operator_client  # noqa: F401
from django.test import Client

pytestmark = pytest.mark.django_db


def login(client, password, ip="203.0.113.7"):
    return client.post(
        f"{ADMIN}login/",
        {"username": "ada", "password": password, "next": ADMIN},
        REMOTE_ADDR=ip,
    )


def test_admin_liegt_nicht_unter_admin(operator_client):  # noqa: F811
    assert operator_client.get("/admin/").status_code == 404


def test_ohne_anmeldung_kein_zugang(client):
    response = client.get(ADMIN)
    assert response.status_code == 302
    assert response["Location"].startswith(f"{ADMIN}login/")


def test_betreiber_meldet_sich_an(operator):  # noqa: F811
    client = Client()
    response = login(client, PASSWORD)
    assert response.status_code == 302
    assert client.get(ADMIN).status_code == 200


def test_wiederholte_fehlversuche_werden_gebremst(operator):  # noqa: F811
    client = Client()
    for _ in range(5):
        assert login(client, "falsch").status_code == 200
    response = login(client, PASSWORD)  # auch das richtige Passwort hilft jetzt nicht
    assert response.status_code == 429
    assert client.get(ADMIN).status_code == 302


def test_bremse_gilt_je_ip(operator):  # noqa: F811
    for _ in range(5):
        login(Client(), "falsch", ip="203.0.113.7")
    assert login(Client(), PASSWORD, ip="198.51.100.9").status_code == 302


def test_ip_wird_nur_als_hash_gespeichert(operator):  # noqa: F811
    from schwarmstack.models import LoginAttempt

    login(Client(), "falsch", ip="203.0.113.7")
    stored = LoginAttempt.objects.get()
    assert "203.0.113.7" not in stored.ip_hash


def test_hinter_dem_proxy_zaehlt_die_ip_aus_x_forwarded_for(operator, settings):  # noqa: F811
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
    assert via_proxy(PASSWORD, "203.0.113.7").status_code == 429
    assert via_proxy(PASSWORD, "198.51.100.9").status_code == 302
