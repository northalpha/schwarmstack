import base64
import json

import pytest
from altcha import Challenge, Payload, solve_challenge
from django import forms
from factories import make_event

from altcha_gate import services
from altcha_gate.forms import AltchaFormMixin
from altcha_gate.models import UsedChallenge


@pytest.fixture(autouse=True)
def schnelle_aufgaben(settings):
    settings.ALTCHA_COST = 50  # nur für die Tests, im Betrieb 5000


def solved_payload() -> str:
    challenge = Challenge.from_dict(services.new_challenge())
    solution = solve_challenge(challenge)
    assert solution is not None
    return Payload(challenge, solution).to_base64()


@pytest.mark.django_db
class TestServices:
    def test_gueltige_loesung(self):
        assert services.verify_payload(solved_payload()) is True

    def test_loesung_gilt_nur_einmal(self):
        payload = solved_payload()
        assert services.verify_payload(payload) is True
        assert services.verify_payload(payload) is False
        assert UsedChallenge.objects.count() == 1

    @pytest.mark.parametrize("payload", [None, "", "kein-base64!", "e30=", "bm9wZQ=="])
    def test_kaputte_eingaben(self, payload):
        assert services.verify_payload(payload) is False

    def test_manipulierte_aufgabe(self):
        data = json.loads(base64.b64decode(solved_payload()))
        data["challenge"]["parameters"]["cost"] = 1
        forged = base64.b64encode(json.dumps(data).encode()).decode()
        assert services.verify_payload(forged) is False

    def test_falsche_loesung(self):
        data = json.loads(base64.b64decode(solved_payload()))
        data["solution"]["counter"] += 1
        forged = base64.b64encode(json.dumps(data).encode()).decode()
        assert services.verify_payload(forged) is False

    def test_abgelaufene_aufgabe(self, settings):
        settings.ALTCHA_EXPIRY_SECONDS = -5
        assert services.verify_payload(solved_payload()) is False

    def test_andere_instanz_mit_anderem_geheimnis(self, settings):
        payload = solved_payload()
        settings.ALTCHA_HMAC_SECRET = "ein-anderes-geheimnis"  # noqa: S105
        assert services.verify_payload(payload) is False

    def test_aufraeumen(self):
        services.verify_payload(solved_payload())
        assert services.purge_old(max_age_hours=0) == 1


@pytest.mark.django_db
def test_endpunkt_liefert_aufgabe(client):
    response = client.get("/altcha/challenge/")
    assert response.status_code == 200
    data = response.json()
    assert data["signature"] and data["parameters"]["algorithm"] == "PBKDF2/SHA-256"
    assert "no-cache" in response["Cache-Control"]
    assert client.post("/altcha/challenge/").status_code == 405


@pytest.mark.django_db
def test_endpunkt_aufgabe_ist_loesbar_und_pruefbar(client):
    challenge = Challenge.from_dict(client.get("/altcha/challenge/").json())
    solution = solve_challenge(challenge)
    assert services.verify_payload(Payload(challenge, solution).to_base64()) is True


class DemoForm(AltchaFormMixin, forms.Form):
    name = forms.CharField()


@pytest.mark.django_db
class TestFormular:
    def test_ausgeschaltet_braucht_kein_feld(self):
        form = DemoForm({"name": "x"}, altcha_enabled=False)
        assert form.is_valid()
        assert "altcha" not in form.fields

    def test_eingeschaltet_ohne_loesung(self):
        form = DemoForm({"name": "x"}, altcha_enabled=True)
        assert not form.is_valid()
        assert "Sicherheitsprüfung" in str(form.non_field_errors())

    def test_eingeschaltet_mit_loesung(self):
        form = DemoForm({"name": "x", "altcha": solved_payload()}, altcha_enabled=True)
        assert form.is_valid()

    def test_event_schalter(self):
        assert make_event().altcha_enabled is False


def test_widget_template_ohne_fremde_quellen(client):
    from django.template.loader import render_to_string

    html = render_to_string("altcha_gate/widget.html")
    assert 'challenge="/altcha/challenge/"' in html
    assert "http://" not in html and "https://" not in html
    assert "<script>" not in html  # kein Inline-JS
