"""Equipment-Foto: freiwillig, mit eigener Einwilligung, bereinigt, nur per App (Ticket #82)."""

import io
import logging
from datetime import timedelta

import pytest
from django.conf import settings as django_settings
from django.contrib.admin.models import LogEntry
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from photo_files import foto
from PIL import Image

from submissions import photos, services
from submissions.models import Campaign, Consent, EquipmentPhoto, Submission

pytestmark = pytest.mark.django_db

DATEINAME = "Garten-Musterstrasse-12.jpg"
HAKEN = {"consent_equipment_photo": "on"}


def datei(format="jpeg", name=DATEINAME, **kwargs):
    return SimpleUploadedFile(name, foto(format, **kwargs), content_type="image/jpeg")


def url(participant, suffix=""):
    return f"/submission/{participant.reference}/{suffix}"


def add_url(participant):
    return url(participant, "aendern/foto/")


def objects(storage_dir):
    """Alle Objekte im lokalen Speicher, als Pfade relativ zum Speicher."""
    root = storage_dir / "objects"
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


def photos_in_storage(storage_dir):
    return [name for name in objects(storage_dir) if "/foto-" in name]


def add(participant, *, haken=True, **kwargs):
    data = {"equipment_photo": datei(**kwargs), **(HAKEN if haken else {})}
    return participant.client.post(add_url(participant), data)


def photo_of(participant):
    """Das Foto der Submission, frisch aus der Datenbank (das Modell merkt sich die Beziehung)."""
    return Submission.objects.get(pk=participant.submission.pk).photo


def photo_consents(participant):
    return Consent.objects.filter(
        submission=participant.submission, kind=Consent.Kind.EQUIPMENT_PHOTO
    ).order_by("granted_at", "pk")


@pytest.fixture
def with_photo(participant):
    add(participant)
    assert photo_of(participant) is not None
    return participant


# -- Anlegen -------------------------------------------------------------------


def test_submission_ohne_foto_bleibt_ohne_foto_und_ohne_einwilligung(participant, storage_dir):
    assert photo_of(participant) is None
    assert not photo_consents(participant).exists()
    assert photos_in_storage(storage_dir) == []
    assert "Equipment-Foto" not in participant.page()


def test_anlegen_mit_foto_und_haekchen_speichert_foto_thumbnail_und_einwilligung(
    campaign, valid_form, storage_dir
):
    from django.test import Client

    client = Client()
    response = client.post("/", {**valid_form, **HAKEN, "equipment_photo": datei()})
    assert response.status_code == 302
    submission = Submission.objects.get()
    stored = submission.photo
    assert sorted(photos_in_storage(storage_dir)) == sorted([stored.key, stored.thumbnail_key])
    (consent,) = submission.consents.filter(kind=Consent.Kind.EQUIPMENT_PHOTO)
    assert consent.text_version == django_settings.CONSENT_TEXT_VERSION
    assert consent.revoked_at is None


def test_anlegen_mit_foto_ohne_haekchen_legt_nichts_an(campaign, valid_form, storage_dir, client):
    response = client.post("/", {**valid_form, "equipment_photo": datei()})
    assert response.status_code == 200
    assert "consent_equipment_photo" in response.context["form"].errors
    assert not Submission.objects.exists()
    assert objects(storage_dir) == []


def test_anlegen_mit_kaputtem_foto_legt_nichts_an(campaign, valid_form, storage_dir, client):
    kaputt = SimpleUploadedFile(DATEINAME, b"kein Bild", content_type="image/jpeg")
    response = client.post("/", {**valid_form, **HAKEN, "equipment_photo": kaputt})
    assert response.status_code == 200
    assert "equipment_photo" in response.context["form"].errors
    assert not Submission.objects.exists()
    assert objects(storage_dir) == []


def test_haekchen_ohne_datei_ist_kein_fehler(campaign, valid_form, storage_dir, client):
    response = client.post("/", {**valid_form, **HAKEN})
    assert response.status_code == 302
    assert Submission.objects.get().photo is None
    assert not Consent.objects.filter(kind=Consent.Kind.EQUIPMENT_PHOTO).exists()


def test_formulare_zeigen_hinweis_und_unangekreuztes_haekchen_an_jedem_upload_feld(
    participant, with_photo
):
    entry = participant.client.get("/neu/").content.decode()
    details = participant.client.get(url(participant, "aendern/")).content.decode()
    ersetzen = participant.client.get(add_url(participant)).content.decode()
    # Ohne Foto zeigt „Angaben ändern“ das Formular zum Hinzufügen, mit Foto nur das Ersetzen.
    ohne_foto, _ = _participant_without_photo(participant)
    hinzufuegen = ohne_foto.client.get(url(ohne_foto, "aendern/")).content.decode()
    for seite in (entry, hinzufuegen, ersetzen):
        assert 'role="note"' in seite
        assert "entfernen wir alle personenbezogenen Daten" in seite
        assert "Gesichter, Hausnummern, Autokennzeichen, Straßenschilder" in seite
        assert 'type="file"' in seite
        assert "multipart/form-data" in seite
        assert "image/heic" in seite
    for seite in (entry, hinzufuegen):
        assert 'name="consent_equipment_photo"' in seite
        assert "checked" not in seite.split('name="consent_equipment_photo"')[1].split(">")[0]
        assert "Ich erlaube, dass das Foto im Rahmen des Projekts verwendet wird." in seite
    assert 'type="file"' not in details  # mit Foto: nur Ersetzen und Löschen als Knöpfe


def _participant_without_photo(participant):
    from uploads_helper import Participant

    ohne = Participant({"credit_name": "Bo", "setup_description": "x", "consent_project_use": "on"})
    return ohne, ohne.submission


# -- Nachträglich hinzufügen ------------------------------------------------------


def test_foto_nachtraeglich_hinzufuegen_mit_einwilligung_und_textversion(participant, storage_dir):
    response = add(participant)
    assert response.status_code == 302
    assert response["Location"] == f"/submission/{participant.reference}/"
    stored = photo_of(participant)
    assert sorted(photos_in_storage(storage_dir)) == sorted([stored.key, stored.thumbnail_key])
    (consent,) = photo_consents(participant)
    assert consent.text_version == django_settings.CONSENT_TEXT_VERSION
    assert consent.revoked_at is None


def test_hinzufuegen_ohne_haekchen_wird_abgelehnt_und_legt_nichts_ab(participant, storage_dir):
    response = add(participant, haken=False)
    assert response.status_code == 200
    assert "consent_equipment_photo" in response.context["form"].errors
    assert photo_of(participant) is None
    assert not photo_consents(participant).exists()
    assert objects(storage_dir) == []


def test_hinzufuegen_ohne_datei_zeigt_einen_fehler(participant, storage_dir):
    response = participant.client.post(add_url(participant), HAKEN)
    assert response.status_code == 200
    assert "equipment_photo" in response.context["form"].errors


@pytest.mark.parametrize("format", ["jpeg", "png", "webp", "heic"])
def test_alle_eingabeformate_lassen_sich_hinzufuegen(participant, storage_dir, format):
    assert add(participant, format=format).status_code == 302
    assert photo_of(participant) is not None


def test_zu_grosse_datei_wird_abgelehnt_ohne_etwas_abzulegen(participant, storage_dir, monkeypatch):
    monkeypatch.setattr(photos, "MAX_BYTES", 1000)
    response = add(participant)
    assert response.status_code == 200
    assert "10 MB" in response.content.decode()
    assert objects(storage_dir) == []
    assert not photo_consents(participant).exists()


@pytest.mark.parametrize(
    "inhalt", [b"", b"kein Bild", b"%PDF-1.7\n" + bytes(200), foto("jpeg")[:300]]
)
def test_kaputte_und_fremde_dateien_werden_abgelehnt(participant, storage_dir, inhalt):
    upload = SimpleUploadedFile(DATEINAME, inhalt)
    response = participant.client.post(add_url(participant), {"equipment_photo": upload, **HAKEN})
    assert response.status_code == 200
    assert photo_of(participant) is None
    assert objects(storage_dir) == []
    assert not photo_consents(participant).exists()


def test_pixelbombe_wird_abgelehnt(participant, storage_dir, monkeypatch):
    monkeypatch.setattr(photos, "MAX_PIXELS", 1000)
    response = add(participant)
    assert response.status_code == 200
    assert "Pixel" in response.content.decode()
    assert objects(storage_dir) == []


# -- Gespeichert wird nur das Bereinigte ------------------------------------------


def test_gespeicherte_dateien_enthalten_keine_metadaten(with_photo, storage_dir):
    from photo_files import GEHEIM_BYTES

    stored = photo_of(with_photo)
    for key in (stored.key, stored.thumbnail_key):
        data = (storage_dir / "objects" / key).read_bytes()
        assert data[:2] == b"\xff\xd8"
        assert b"Exif" not in data and b"xap" not in data
        assert not any(text in data for text in GEHEIM_BYTES)
        with Image.open(io.BytesIO(data)) as image:
            assert len(image.getexif()) == 0


def test_dateiname_der_teilnehmenden_taucht_nirgends_auf(
    participant, storage_dir, operator_client, caplog
):
    with caplog.at_level(logging.DEBUG):
        add(participant)
        participant.client.get(url(participant, "foto/"))
        participant.client.get(url(participant, "foto/vorschau/"))
    stored = photo_of(participant)
    assert "Musterstrasse" not in stored.key + stored.thumbnail_key
    assert "Musterstrasse" not in " ".join(objects(storage_dir))
    assert "Musterstrasse" not in caplog.text
    felder = [
        *Submission.objects.values_list("credit_name", "setup_description"),
        *EquipmentPhoto.objects.values_list("key", "thumbnail_key"),
        *LogEntry.objects.values_list("object_repr", "change_message"),
    ]
    assert "Musterstrasse" not in repr(felder)


def test_schluessel_entstehen_aus_submission_id_und_zufall(participant):
    add(participant)
    stored = photo_of(participant)
    assert stored.key.startswith(f"{participant.reference}/foto-")
    assert stored.thumbnail_key != stored.key


def test_scheitert_das_speichern_bleibt_nichts_im_speicher(participant, storage_dir, monkeypatch):
    def kaputt(*args, **kwargs):
        raise RuntimeError("Datenbank weg")

    monkeypatch.setattr(EquipmentPhoto.objects, "create", kaputt)
    from django.test import Client

    participant.client.raise_request_exception = False
    response = add(participant)
    assert response.status_code == 500
    assert objects(storage_dir) == []
    assert not photo_consents(participant).exists()
    assert isinstance(participant.client, Client)


# -- Anzeigen ----------------------------------------------------------------------


def test_seitenleiste_zeigt_thumbnail_unter_setup_und_verlinkt_das_foto(with_photo):
    seite = with_photo.page()
    reference = with_photo.reference
    assert f'href="/submission/{reference}/foto/"' in seite
    assert f'src="/submission/{reference}/foto/vorschau/"' in seite
    assert 'aria-label="Equipment-Foto in voller Größe öffnen"' in seite
    assert 'alt="Dein Equipment-Foto (Vorschau)"' in seite
    seitenleiste = seite.split('<aside class="side">')[1].split("</aside>")[0]
    assert seitenleiste.index("Setup") < seitenleiste.index("Equipment-Foto")
    assert seitenleiste.index("Equipment-Foto") < seitenleiste.index("Angaben ändern")


def test_ohne_foto_steht_in_der_seitenleiste_nichts(participant):
    seitenleiste = participant.page().split('<aside class="side">')[1].split("</aside>")[0]
    assert "Equipment-Foto" not in seitenleiste
    assert "vorschau" not in seitenleiste


def test_foto_und_thumbnail_werden_ueber_die_app_ausgeliefert(with_photo):
    voll = with_photo.client.get(url(with_photo, "foto/"))
    klein = with_photo.client.get(url(with_photo, "foto/vorschau/"))
    assert voll.status_code == klein.status_code == 200
    assert voll["Content-Type"] == "image/jpeg"
    assert "no-store" in voll["Cache-Control"]
    assert b"".join(voll.streaming_content if voll.streaming else [voll.content])[:2] == b"\xff\xd8"
    with Image.open(io.BytesIO(klein.content)) as bild:
        assert max(bild.size) <= 504


def test_details_seite_zeigt_foto_datum_und_knoepfe(with_photo):
    seite = with_photo.client.get(url(with_photo, "aendern/")).content.decode()
    assert "Equipment-Foto (freiwillig)" in seite
    assert "Standort und Gerätedaten wurden beim Hochladen entfernt." in seite
    assert "Foto ersetzen" in seite and "Foto löschen" in seite
    assert "Löschen widerruft deine Einwilligung zur Nutzung des Fotos." in seite
    assert timezone.now().strftime("%Y") in seite


def test_fremde_submission_bekommt_404_auch_fuer_das_thumbnail(with_photo, another):
    fremd = another()
    for suffix in ("foto/", "foto/vorschau/", "aendern/foto/", "aendern/foto/loeschen/"):
        pfad = f"/submission/{with_photo.reference}/{suffix}"
        assert fremd.client.get(pfad).status_code == 404, pfad
    assert (
        fremd.client.post(add_url(with_photo), {"equipment_photo": datei(), **HAKEN}).status_code
        == 404
    )
    assert (
        fremd.client.post(f"/submission/{with_photo.reference}/aendern/foto/loeschen/").status_code
        == 404
    )
    assert photo_of(with_photo) is not None


def test_ohne_foto_gibt_es_404_statt_bild(participant):
    assert participant.client.get(url(participant, "foto/")).status_code == 404
    assert participant.client.get(url(participant, "foto/vorschau/")).status_code == 404


# -- Löschen und erneut hinzufügen ----------------------------------------------------


def test_loeschen_fragt_erst_nach(with_photo, storage_dir):
    response = with_photo.client.get(url(with_photo, "aendern/foto/loeschen/"))
    assert response.status_code == 200
    assert "Equipment-Foto löschen" in response.content.decode()
    assert len(photos_in_storage(storage_dir)) == 2


def test_loeschen_entfernt_foto_und_thumbnail_und_vermerkt_den_widerruf(with_photo, storage_dir):
    response = with_photo.client.post(url(with_photo, "aendern/foto/loeschen/"))
    assert response.status_code == 302
    assert photos_in_storage(storage_dir) == []
    assert photo_of(with_photo) is None
    (consent,) = photo_consents(with_photo)
    assert consent.revoked_at is not None
    assert with_photo.client.get(url(with_photo, "foto/")).status_code == 404
    assert with_photo.client.get(url(with_photo, "foto/vorschau/")).status_code == 404
    eintrag = LogEntry.objects.latest("action_time")
    assert "Equipment-Foto gelöscht" in eintrag.change_message
    assert eintrag.user.username == services.PARTICIPANT_USERNAME


def test_erneutes_hinzufuegen_nach_dem_loeschen_erteilt_eine_neue_einwilligung(
    with_photo, storage_dir
):
    with_photo.client.post(url(with_photo, "aendern/foto/loeschen/"))
    assert add(with_photo, haken=False).status_code == 200  # ohne Häkchen geht es nicht
    assert add(with_photo).status_code == 302
    alt, neu = photo_consents(with_photo)
    assert alt.revoked_at is not None
    assert neu.revoked_at is None and neu.granted_at >= alt.granted_at
    assert len(photos_in_storage(storage_dir)) == 2


def test_je_zweck_gilt_hoechstens_eine_nicht_widerrufene_einwilligung(with_photo):
    from django.db import IntegrityError, transaction

    with pytest.raises(IntegrityError), transaction.atomic():
        Consent.objects.create(
            submission=with_photo.submission,
            kind=Consent.Kind.EQUIPMENT_PHOTO,
            text_version="x",
        )


# -- Ersetzen ---------------------------------------------------------------------


def test_ersetzen_loescht_die_alten_dateien_und_behaelt_die_einwilligung(with_photo, storage_dir):
    alt = photo_of(with_photo)
    alte_dateien = {alt.key, alt.thumbnail_key}
    response = with_photo.client.post(add_url(with_photo), {"equipment_photo": datei("png")})
    assert response.status_code == 302, response.content.decode()
    neu = Submission.objects.get(pk=with_photo.submission.pk).photo
    assert {neu.key, neu.thumbnail_key}.isdisjoint(alte_dateien)
    assert sorted(photos_in_storage(storage_dir)) == sorted([neu.key, neu.thumbnail_key])
    (consent,) = photo_consents(with_photo)  # keine neue: sie gilt weiter
    assert consent.revoked_at is None


def test_ersetzen_verlangt_nur_bei_geaenderter_textversion_eine_neue_einwilligung(
    with_photo, settings
):
    settings.CONSENT_TEXT_VERSION = "2027-01"
    ohne = with_photo.client.post(add_url(with_photo), {"equipment_photo": datei()})
    assert ohne.status_code == 200
    assert "consent_equipment_photo" in ohne.context["form"].errors
    mit = with_photo.client.post(add_url(with_photo), {"equipment_photo": datei(), **HAKEN})
    assert mit.status_code == 302
    alt, neu = photo_consents(with_photo)
    assert alt.revoked_at is not None and alt.text_version != "2027-01"
    assert neu.revoked_at is None and neu.text_version == "2027-01"


def test_ersetzen_zeigt_kein_haekchen_solange_die_einwilligung_gilt(with_photo):
    seite = with_photo.client.get(add_url(with_photo)).content.decode()
    assert 'name="consent_equipment_photo"' not in seite
    assert "gilt weiter" in seite


def test_ersetzen_mit_kaputtem_foto_laesst_das_alte_stehen(with_photo, storage_dir):
    vorher = objects(storage_dir)
    kaputt = SimpleUploadedFile(DATEINAME, b"kein Bild")
    assert (
        with_photo.client.post(add_url(with_photo), {"equipment_photo": kaputt}).status_code == 200
    )
    assert objects(storage_dir) == vorher


# -- Unabhängig von den übrigen Angaben ---------------------------------------------------


def test_foto_aendern_ohne_die_uebrigen_angaben_anzufassen(participant):
    vorher = (participant.submission.credit_name, participant.submission.setup_description)
    add(participant)
    submission = Submission.objects.get(pk=participant.submission.pk)
    assert (submission.credit_name, submission.setup_description) == vorher


def test_angaben_aendern_ohne_das_foto_anzufassen(with_photo, storage_dir):
    vorher = photo_of(with_photo).key
    response = with_photo.client.post(
        url(with_photo, "aendern/"), {"credit_name": "Ada S.", "setup_description": "Neu"}
    )
    assert response.status_code == 302
    submission = Submission.objects.get(pk=with_photo.submission.pk)
    assert submission.setup_description == "Neu"
    assert submission.photo.key == vorher
    assert len(photos_in_storage(storage_dir)) == 2
    assert (
        not LogEntry.objects.filter(change_message__contains="Equipment-Foto")
        .exclude(change_message__contains="hinzugefügt")
        .exists()
    )


def test_foto_aenderungen_stehen_im_protokoll_ohne_dateinamen(participant):
    add(participant)
    add(participant, name="anderes-Foto-Ort.jpg")
    meldungen = list(
        LogEntry.objects.order_by("action_time").values_list("change_message", flat=True)
    )
    assert any("Equipment-Foto hinzugefügt (durch Teilnehmende)" in m for m in meldungen)
    assert any("Equipment-Foto ersetzt (durch Teilnehmende)" in m for m in meldungen)
    assert not any("Ort" in m for m in meldungen)


# -- Zeitfenster ------------------------------------------------------------------------------


@pytest.fixture
def ended(campaign):
    Campaign.objects.update(
        starts_at=timezone.now() - timedelta(days=3), ends_at=timezone.now() - timedelta(hours=1)
    )


def test_nach_dem_ende_der_aktion_ist_das_foto_schreibgeschuetzt(with_photo, storage_dir, ended):
    vorher = objects(storage_dir)
    assert add(with_photo).status_code == 302
    assert with_photo.client.post(url(with_photo, "aendern/foto/loeschen/")).status_code == 302
    assert objects(storage_dir) == vorher
    assert photo_of(with_photo) is not None
    assert with_photo.client.get(url(with_photo, "foto/")).status_code == 200  # ansehen geht
    seite = with_photo.page()
    assert "foto/vorschau/" in seite and "Angaben ändern" not in seite


def test_nach_dem_ende_laesst_sich_kein_foto_hinzufuegen(participant, storage_dir, ended):
    add(participant)
    assert photo_of(participant) is None
    assert objects(storage_dir) == []


# -- Löschung der Submission ----------------------------------------------------------


def test_loeschung_der_submission_entfernt_foto_thumbnail_und_einwilligung(with_photo, storage_dir):
    with_photo.client.post(url(with_photo, "loeschen/"))
    assert photos_in_storage(storage_dir) == []
    assert not EquipmentPhoto.objects.exists()
    assert not photo_consents(with_photo).exists()
    assert with_photo.client.get(url(with_photo, "foto/")).status_code == 404


def test_gleichzeitige_loeschung_laesst_kein_foto_zurueck(with_photo, storage_dir):
    services.delete_submission(with_photo.submission, by=Submission.DeletedBy.PARTICIPANT)
    foto_neu = photos.clean(io.BytesIO(foto("jpeg")))
    with pytest.raises(services.PhotoNotAllowed):
        services.add_photo(with_photo.submission, foto_neu, consent_given=True)
    assert photos_in_storage(storage_dir) == []


def test_widerruf_der_namensnennung_laesst_das_foto_stehen(with_photo, storage_dir):
    antwort = with_photo.client.post(url(with_photo, "namensnennung/widerrufen/"))
    assert antwort.status_code == 302
    assert photo_of(with_photo) is not None
    assert len(photos_in_storage(storage_dir)) == 2
    (consent,) = photo_consents(with_photo)
    assert consent.revoked_at is None
