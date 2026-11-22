import pytest
from factories import GIB, make_event, make_file, make_stack, make_submission

from submissions.models import ExposureLine, Stack
from submissions.tokens import hash_token, new_token

MIB = 1024**2

STACK = {
    "object_name": "Andromedagalaxie",
    "capture_dates": "10.–12.11.2026",
    "telescope": "Refraktor 80/400",
    "focal_length_mm": "400",
    "aperture_mm": "80",
    "camera": "ASI294MC",
    "mount": "EQ6-R",
    "filters": "L-Ultimate",
    "has_flats": "on",
    "exposure_lines-TOTAL_FORMS": "4",
    "exposure_lines-INITIAL_FORMS": "0",
    "exposure_lines-MIN_NUM_FORMS": "0",
    "exposure_lines-MAX_NUM_FORMS": "1000",
    "exposure_lines-0-filter": "Ha",
    "exposure_lines-0-count": "42",
    "exposure_lines-0-seconds": "300",
    "exposure_lines-0-gain_iso": "120",
    "exposure_lines-0-sensor_temp_c": "-10",
    "exposure_lines-1-filter": "OIII",
    "exposure_lines-1-count": "20",
    "exposure_lines-1-seconds": "300",
}


@pytest.fixture
def angemeldet(client, db):
    token = new_token()
    submission = make_submission(
        make_event(quota_bytes_per_submission=GIB), token_hash=hash_token(token)
    )
    client.cookies["abgabe_token"] = token
    return client, submission, token


@pytest.mark.django_db
class TestLink:
    def test_gueltiger_link_setzt_cookie_und_leitet_weiter(self, client):
        token = new_token()
        make_submission(token_hash=hash_token(token))
        response = client.get(f"/a/{token}/")
        assert response.status_code == 302 and response["Location"] == "/abgabe/"
        assert response.cookies["abgabe_token"].value == token
        assert client.get("/abgabe/").status_code == 200

    def test_falscher_link(self, client, db):
        response = client.get("/a/falsch/")
        assert response.status_code == 403
        assert "abgabe_token" not in response.cookies

    def test_abgabeseite_ohne_cookie(self, client, db):
        assert client.get("/abgabe/").status_code == 403

    def test_abgabeseite_mit_falschem_cookie(self, client, db):
        client.cookies["abgabe_token"] = "gibt-es-nicht"  # noqa: S105
        assert client.get("/abgabe/").status_code == 403

    def test_last_seen_wird_gesetzt(self, angemeldet):
        client, submission, _ = angemeldet
        client.get("/abgabe/")
        submission.refresh_from_db()
        assert submission.last_seen_at is not None


@pytest.mark.django_db
class TestSeite:
    def test_name_und_quotenbalken(self, angemeldet):
        client, submission, _ = angemeldet
        stack = make_stack(submission)
        make_file(stack, 256 * MIB)
        make_file(stack, 999 * MIB, state="rejected", name="x.fits")  # zählt nicht
        text = client.get("/abgabe/").content.decode()
        assert submission.display_name in text
        assert "256 MiB" in text and "1,00 GiB" in text
        assert 'value="25"' in text and "style=" not in text

    def test_stack_karte_zeigt_status_und_belichtung(self, angemeldet):
        client, submission, _ = angemeldet
        stack = make_stack(submission, object_name="M42")
        ExposureLine.objects.create(stack=stack, filter="Ha", count=42, seconds=300)
        text = client.get("/abgabe/").content.decode()
        assert "M42" in text and "Offen – Dateien hinzufügen" in text
        assert "3 h 30 min" in text

    def test_fremde_stacks_sind_nicht_sichtbar(self, angemeldet):
        client, submission, _ = angemeldet
        make_stack(make_submission(submission.event), object_name="Fremdes Objekt")
        assert "Fremdes Objekt" not in client.get("/abgabe/").content.decode()

    def test_gesperrt_kein_formular(self, angemeldet):
        client, submission, _ = angemeldet
        submission.is_blocked = True
        submission.save()
        text = client.get("/abgabe/").content.decode()
        assert "gesperrt" in text and "Stack anlegen" not in text
        assert client.post("/abgabe/", STACK).status_code == 200
        assert Stack.objects.count() == 0

    def test_geschlossenes_event_kein_formular(self, angemeldet):
        client, submission, _ = angemeldet
        submission.event.active = False
        submission.event.save()
        assert "Stack anlegen" not in client.get("/abgabe/").content.decode()
        client.post("/abgabe/", STACK)
        assert Stack.objects.count() == 0


@pytest.mark.django_db
class TestStackAnlegen:
    def test_legt_stack_mit_belichtung_an(self, angemeldet):
        client, submission, _ = angemeldet
        response = client.post("/abgabe/", STACK)
        assert response.status_code == 302
        stack = Stack.objects.get()
        assert stack.submission == submission and stack.state == "open"
        assert float(stack.focal_ratio) == 5.0  # 400 / 80
        assert stack.has_flats and not stack.has_darks
        assert stack.exposure_lines.count() == 2  # leere Zeilen werden ignoriert
        assert stack.total_exposure_seconds == 62 * 300

    @pytest.mark.parametrize("fehlt", ["object_name", "telescope", "camera"])
    def test_pflichtfelder(self, angemeldet, fehlt):
        client, _, _ = angemeldet
        response = client.post("/abgabe/", {**STACK, fehlt: ""})
        assert response.status_code == 200 and Stack.objects.count() == 0

    def test_mindestens_eine_belichtungszeile(self, angemeldet):
        client, _, _ = angemeldet
        data = {
            k: v
            for k, v in STACK.items()
            if not k.startswith("exposure_lines-0") and not k.startswith("exposure_lines-1")
        }
        response = client.post("/abgabe/", data)
        assert response.status_code == 200 and Stack.objects.count() == 0
        assert "mindestens eine Belichtungszeile" in response.content.decode()

    def test_halb_ausgefuellte_zeile_ist_ein_fehler(self, angemeldet):
        client, _, _ = angemeldet
        response = client.post("/abgabe/", {**STACK, "exposure_lines-1-count": ""})
        assert response.status_code == 200 and Stack.objects.count() == 0

    def test_anzahl_und_sekunden_muessen_positiv_sein(self, angemeldet):
        client, _, _ = angemeldet
        for feld, wert in (("exposure_lines-0-count", "0"), ("exposure_lines-0-seconds", "-5")):
            assert client.post("/abgabe/", {**STACK, feld: wert}).status_code == 200
        assert Stack.objects.count() == 0

    def test_ausruestung_wird_vom_letzten_stack_vorausgefuellt(self, angemeldet):
        client, submission, _ = angemeldet
        client.post("/abgabe/", STACK)
        form = client.get("/abgabe/").context["stack_form"]
        assert form.initial["telescope"] == "Refraktor 80/400"
        assert form.initial["camera"] == "ASI294MC"
        assert form.initial["has_flats"] is True
        assert "object_name" not in form.initial  # Objekt ist je Stack neu

    def test_erster_stack_ohne_vorbelegung(self, angemeldet):
        client, _, _ = angemeldet
        assert client.get("/abgabe/").context["stack_form"].initial == {}


@pytest.mark.django_db
class TestRechtliches:
    def test_seiten_sind_erreichbar(self, client, settings):
        settings.OPERATOR_NAME = "Testsystem (Platzhalter)"
        settings.OPERATOR_EMAIL = "kontakt@example.org"
        settings.PRIVACY_EXTRA_PROCESSORS = ["Tailscale Inc. (Testzugang)"]
        text = client.get("/datenschutz/").content.decode()
        assert "Testsystem (Platzhalter)" in text and "kontakt@example.org" in text
        assert "Tailscale Inc." in text and "Referer" not in text.replace("Beim Aufruf", "")
        assert "Impressum" in client.get("/impressum/").content.decode()

    def test_testsystem_hinweis(self, client, settings):
        settings.TEST_SYSTEM = True
        assert "Testsystem – Daten werden gelöscht" in client.get("/").content.decode()
        settings.TEST_SYSTEM = False
        assert "Daten werden gelöscht" not in client.get("/").content.decode()

    def test_keine_externen_quellen(self, client):
        for url in ("/", "/datenschutz/", "/impressum/"):
            html = client.get(url).content.decode()
            assert "http://" not in html.replace("http://www.w3.org", "")
            assert "<script>" not in html
