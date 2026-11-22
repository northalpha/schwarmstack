import pytest
from django.core import signing
from factories import make_event

from entry import tickets
from entry.models import EntryAttempt
from entry.origin import origin_allowed, origin_of

ORIGIN = "https://projekt.example.org"


@pytest.fixture
def event(db):
    return make_event(
        entry_origins=[ORIGIN, "https://demo.example.org:10000"],
        entry_page_url="https://projekt.example.org/",
    )


class TestOrigin:
    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            ("https://Projekt.Example.org/seite?x=1#a", "https://projekt.example.org"),
            ("https://projekt.example.org:443/", "https://projekt.example.org"),
            ("https://demo.example.org:10000/", "https://demo.example.org:10000"),
            ("http://projekt.example.org/", None),
            ("", None),
            ("projekt.example.org", None),
            ("https://", None),
            ("https://host:abc/", None),
        ],
    )
    def test_origin_of(self, url, expected):
        assert origin_of(url) == expected

    def test_erlaubt(self):
        allowed = [ORIGIN, "https://demo.example.org:10000"]
        assert origin_allowed("https://projekt.example.org/irgendwas", allowed)
        assert origin_allowed("https://demo.example.org:10000/", allowed)

    @pytest.mark.parametrize(
        "referer",
        [
            "",
            "http://projekt.example.org/",
            "https://projekt.example.org.böse.de/",
            "https://evil.example.com/https://projekt.example.org",
            "https://demo.example.org/",
            "https://demo.example.org:10001/",
        ],
    )
    def test_nicht_erlaubt(self, referer):
        assert not origin_allowed(referer, [ORIGIN, "https://demo.example.org:10000"])


@pytest.mark.django_db
class TestStart:
    def test_mit_passendem_referer_gibt_es_ticket_und_weiterleitung(self, client, event):
        response = client.get("/start/demo/", HTTP_REFERER=ORIGIN + "/upload-seite")
        assert response.status_code == 302
        assert response["Location"] == "/teilnahme/demo/"
        cookie = response.cookies["entry_ticket"]
        assert cookie["httponly"] and cookie["samesite"] == "Lax"
        assert cookie["max-age"] == 3600
        assert EntryAttempt.objects.get().accepted is True

    @pytest.mark.parametrize(
        "referer", [None, "", "http://projekt.example.org/", "https://evil.example.com/"]
    )
    def test_ohne_oder_mit_falschem_referer_hinweisseite(self, client, event, referer):
        extra = {} if referer is None else {"HTTP_REFERER": referer}
        response = client.get("/start/demo/", **extra)
        assert response.status_code == 403
        assert "entry_ticket" not in response.cookies
        text = response.content.decode()
        assert "Bitte starte über die Projektseite" in text
        assert "https://projekt.example.org/" in text  # Link zurück
        assert "Referer" not in text and "Origin" not in text  # erklärt das Verfahren nicht
        assert EntryAttempt.objects.get().accepted is False

    def test_unbekanntes_event_sieht_gleich_aus(self, client, db):
        response = client.get("/start/gibt-es-nicht/", HTTP_REFERER=ORIGIN)
        assert response.status_code == 403
        assert "Bitte starte über die Projektseite" in response.content.decode()

    def test_geschlossenes_event(self, client, event):
        event.active = False
        event.save()
        assert client.get("/start/demo/", HTTP_REFERER=ORIGIN).status_code == 403

    def test_referer_wird_nicht_gespeichert(self, client, event):
        client.get("/start/demo/", HTTP_REFERER=ORIGIN + "/geheim?token=abc")
        values = " ".join(str(v) for row in EntryAttempt.objects.values_list() for v in row)
        assert "geheim" not in values and "token=abc" not in values

    def test_nur_get(self, client, event):
        assert client.post("/start/demo/", HTTP_REFERER=ORIGIN).status_code == 405

    def test_rate_limit_je_ip(self, client, event, settings):
        settings.RATE_ENTRY_PER_HOUR = 3
        for _ in range(3):
            client.get("/start/demo/", HTTP_REFERER=ORIGIN, REMOTE_ADDR="203.0.113.5")
        response = client.get("/start/demo/", HTTP_REFERER=ORIGIN, REMOTE_ADDR="203.0.113.5")
        assert response.status_code == 429
        other = client.get("/start/demo/", HTTP_REFERER=ORIGIN, REMOTE_ADDR="203.0.113.6")
        assert other.status_code == 302  # andere Adresse ist nicht betroffen

    def test_keine_klartext_ip_gespeichert(self, client, event):
        client.get("/start/demo/", HTTP_REFERER=ORIGIN, REMOTE_ADDR="203.0.113.5")
        assert "203.0.113.5" not in EntryAttempt.objects.get().ip_hash


@pytest.mark.django_db
class TestTicket:
    def issue(self, event):
        from django.http import HttpResponse

        response = HttpResponse()
        tickets.issue(response, event)
        return response.cookies["entry_ticket"].value

    def request_with(self, rf, value):
        request = rf.get("/")
        if value is not None:
            request.COOKIES["entry_ticket"] = value
        return request

    def test_gueltig(self, rf, event):
        assert tickets.valid_for(self.request_with(rf, self.issue(event)), event)

    def test_ohne_cookie(self, rf, event):
        assert not tickets.valid_for(self.request_with(rf, None), event)

    def test_manipuliert(self, rf, event):
        value = self.issue(event)
        assert not tickets.valid_for(self.request_with(rf, value[:-2] + "xx"), event)

    def test_fremdes_event(self, rf, event):
        other = make_event(slug="anders")
        assert not tickets.valid_for(self.request_with(rf, self.issue(event)), other)

    def test_abgelaufen(self, rf, event, settings):
        value = self.issue(event)
        settings.ENTRY_TICKET_MAX_AGE = -1
        assert not tickets.valid_for(self.request_with(rf, value), event)

    def test_mit_falschem_salz_signiert(self, rf, event):
        forged = signing.dumps({"event": event.pk}, salt="anderes-salz")
        assert not tickets.valid_for(self.request_with(rf, forged), event)
