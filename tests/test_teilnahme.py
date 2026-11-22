import pytest
from altcha import Challenge, Payload, solve_challenge
from factories import make_event

from altcha_gate import services as altcha
from entry import tickets
from submissions.models import Consent, SocialLink, Submission
from submissions.tokens import hash_token

ORIGIN = "https://projekt.example.org"
VALID = {
    "display_name": "Ada Lovelace",
    "email": "ada@example.org",
    "region": "Brandenburg",
    "bortle": "4",
    "link1": "https://www.astrobin.com/users/ada/",
    "privacy_read": "on",
    "project_use": "on",
    "publish_name_links": "on",
}


@pytest.fixture
def event(db):
    return make_event(entry_origins=[ORIGIN], entry_page_url=ORIGIN + "/")


@pytest.fixture
def mit_ticket(client, event):
    client.get("/start/demo/", HTTP_REFERER=ORIGIN)
    return client


def post(client, data=None, **extra):
    return client.post("/teilnahme/demo/", {**VALID, **(data or {})}, **extra)


@pytest.mark.django_db
class TestZugang:
    def test_ohne_ticket_kein_formular(self, client, event):
        response = client.get("/teilnahme/demo/")
        assert response.status_code == 403
        assert "Bitte starte über die Projektseite" in response.content.decode()

    def test_ohne_ticket_keine_abgabe_moeglich(self, client, event):
        response = post(client)
        assert response.status_code == 403
        assert Submission.objects.count() == 0

    def test_mit_ticket_kommt_das_formular(self, mit_ticket):
        response = mit_ticket.get("/teilnahme/demo/")
        assert response.status_code == 200
        text = response.content.decode()
        assert "Anzeigename" in text and "Datenschutzhinweise" in text

    def test_ticket_gilt_nur_fuer_sein_event(self, client, event):
        make_event(slug="anderes", entry_origins=[ORIGIN])
        client.get("/start/demo/", HTTP_REFERER=ORIGIN)
        assert client.get("/teilnahme/anderes/").status_code == 403

    def test_geschlossenes_event(self, mit_ticket, event):
        event.active = False
        event.save()
        assert mit_ticket.get("/teilnahme/demo/").status_code == 403

    def test_altcha_widget_nur_wenn_eingeschaltet(self, mit_ticket, event):
        assert "altcha-widget" not in mit_ticket.get("/teilnahme/demo/").content.decode()
        event.altcha_enabled = True
        event.save()
        assert "altcha-widget" in mit_ticket.get("/teilnahme/demo/").content.decode()


@pytest.mark.django_db
class TestAnlegen:
    def test_legt_abgabe_an(self, mit_ticket):
        response = post(mit_ticket, REMOTE_ADDR="203.0.113.5")
        assert response.status_code == 200
        sub = Submission.objects.get()
        assert sub.display_name == "Ada Lovelace" and sub.bortle == 4
        assert sub.event.slug == "demo"
        assert "203.0.113.5" not in sub.ip_hash and len(sub.ip_hash) == 64

    def test_token_wird_einmal_angezeigt_und_nur_als_hash_gespeichert(self, mit_ticket):
        response = post(mit_ticket)
        text = response.content.decode()
        token = response.cookies["abgabe_token"].value
        assert f"/a/{token}/" in text
        sub = Submission.objects.get()
        assert sub.token_hash == hash_token(token)
        assert token not in sub.token_hash
        cookie = response.cookies["abgabe_token"]
        assert cookie["httponly"] and cookie["samesite"] == "Lax"

    def test_einwilligungen_werden_festgehalten(self, mit_ticket):
        post(mit_ticket)
        consents = {c.kind: c for c in Consent.objects.all()}
        assert len(consents) == 5
        assert consents["privacy_read"].granted and consents["privacy_read"].granted_at
        assert consents["project_use"].granted
        assert consents["publish_name_links"].granted
        assert not consents["publish_equipment_photo"].granted
        assert not consents["status_mails"].granted
        assert consents["privacy_read"].text_version == "2026-11"

    def test_links_mit_plattform(self, mit_ticket):
        post(mit_ticket, {"link2": "https://example.org/mein-blog"})
        platforms = sorted(SocialLink.objects.values_list("platform", flat=True))
        assert platforms == ["AstroBin", "Webseite"]

    def test_ticket_ist_danach_verbraucht(self, mit_ticket):
        post(mit_ticket)
        assert mit_ticket.get("/teilnahme/demo/").status_code == 403
        assert post(mit_ticket).status_code == 403
        assert Submission.objects.count() == 1

    @pytest.mark.parametrize("fehlend", ["privacy_read", "project_use"])
    def test_pflicht_einwilligungen(self, mit_ticket, fehlend):
        data = {k: v for k, v in VALID.items() if k != fehlend}
        response = mit_ticket.post("/teilnahme/demo/", data)
        assert response.status_code == 200
        assert Submission.objects.count() == 0
        assert "fehler" in response.content.decode()

    def test_status_mails_brauchen_eine_adresse(self, mit_ticket):
        response = post(mit_ticket, {"status_mails": "on", "email": ""})
        assert Submission.objects.count() == 0
        assert "brauchen wir deine E-Mail" in response.content.decode()

    @pytest.mark.parametrize(
        "daten",
        [
            {"display_name": "A"},
            {"display_name": "x" * 81},
            {"bortle": "10"},
            {"bortle": "0"},
            {"email": "kein-mail"},
            {"link1": "http://unsicher.example.org"},
            {"link3": "kein-link"},
        ],
    )
    def test_ungueltige_eingaben(self, mit_ticket, daten):
        response = post(mit_ticket, daten)
        assert response.status_code == 200
        assert Submission.objects.count() == 0

    def test_optionale_felder_duerfen_fehlen(self, mit_ticket):
        data = {k: VALID[k] for k in ("display_name", "privacy_read", "project_use")}
        assert mit_ticket.post("/teilnahme/demo/", data).status_code == 200
        assert Submission.objects.get().email == ""

    def test_rate_limit_neue_abgaben_je_ip(self, client, event, settings):
        settings.RATE_SUBMISSIONS_PER_HOUR = 2
        settings.RATE_ENTRY_PER_HOUR = 100
        for _ in range(2):
            client.get("/start/demo/", HTTP_REFERER=ORIGIN, REMOTE_ADDR="203.0.113.5")
            assert post(client, REMOTE_ADDR="203.0.113.5").status_code == 200
        client.get("/start/demo/", HTTP_REFERER=ORIGIN, REMOTE_ADDR="203.0.113.5")
        assert post(client, REMOTE_ADDR="203.0.113.5").status_code == 429
        assert Submission.objects.count() == 2
        client.get("/start/demo/", HTTP_REFERER=ORIGIN, REMOTE_ADDR="203.0.113.9")
        assert post(client, REMOTE_ADDR="203.0.113.9").status_code == 200


@pytest.mark.django_db
class TestAltcha:
    @pytest.fixture(autouse=True)
    def schnell(self, settings):
        settings.ALTCHA_COST = 50

    def test_ohne_loesung_abgelehnt(self, client, event):
        event.altcha_enabled = True
        event.save()
        client.get("/start/demo/", HTTP_REFERER=ORIGIN)
        response = post(client)
        assert response.status_code == 200 and Submission.objects.count() == 0
        assert "Sicherheitsprüfung" in response.content.decode()

    def test_mit_loesung_angenommen(self, client, event):
        event.altcha_enabled = True
        event.save()
        client.get("/start/demo/", HTTP_REFERER=ORIGIN)
        challenge = Challenge.from_dict(altcha.new_challenge())
        payload = Payload(challenge, solve_challenge(challenge)).to_base64()
        assert post(client, {"altcha": payload}).status_code == 200
        assert Submission.objects.count() == 1


@pytest.mark.django_db
def test_ticket_kann_nicht_fuer_andere_event_ticket_fremd(client, event):
    # ein gültiges Ticket gehört zu genau einem Event
    from django.http import HttpResponse

    other = make_event(slug="zweites", entry_origins=[ORIGIN])
    response = HttpResponse()
    tickets.issue(response, other)
    client.cookies["entry_ticket"] = response.cookies["entry_ticket"].value
    assert client.get("/teilnahme/demo/").status_code == 403
