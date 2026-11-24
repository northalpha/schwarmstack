"""Unterbrochenen Upload fortsetzen und Nachfrist (Ticket #16)."""

import hashlib
import re
from datetime import timedelta

import pytest
from django.utils import timezone
from files import fits
from uploads_helper import complete, create, finish, send_parts, sign, start, upload

from submissions import services
from submissions.models import Master, Submission
from submissions.uploads import may_start, shows_uploader

pytestmark = pytest.mark.django_db


@pytest.fixture
def storage_dir(settings, tmp_path):
    settings.STORAGE_LOCAL_DIR = tmp_path / "speicher"
    return settings.STORAGE_LOCAL_DIR


def ended(campaign, ago):
    """Lässt die Aktion vor `ago` enden (Nachfrist 6 Stunden)."""
    campaign.ends_at = timezone.now() - ago
    campaign.save()


def page(client, reference):
    return client.get(f"/abgabe/{reference}/").content.decode()


def interrupted(client, reference, data, parts_sent=1, part_size=1024):
    """Startet einen Upload und bricht nach einigen Teilen ab, wie ein geschlossener Browser."""
    body = start(client, reference, size=len(data), filename="m101_L.fits").json()
    upload_id = create(client, body["url"])
    send_parts(
        client, reference, body["masterId"], body["key"], upload_id,
        data[: parts_sent * part_size], part_size,
    )  # fmt: skip
    return body, upload_id


# -- Fortsetzen --------------------------------------------------------------


def test_abgabeseite_liefert_daten_zum_fortsetzen(client, reference):
    body, upload_id = interrupted(client, reference, fits(width=100, height=100))
    content = page(client, reference)
    assert f'data-master-id="{body["masterId"]}"' in content
    assert f'data-key="{body["key"]}"' in content
    assert f'data-upload-id="{upload_id}"' in content
    assert 'data-name="m101_L.fits"' in content
    assert "unterbrochen" in content


def test_ohne_upload_id_nichts_zum_fortsetzen(client, reference):
    start(client, reference, size=10)  # nie angelegt: Uppy fängt beim nächsten Mal neu an
    assert "data-upload-id=" not in page(client, reference)


def test_fortsetzen_ueber_die_liste_der_teile(client, reference, storage_dir):
    data = fits(width=100, height=100)
    body, upload_id = interrupted(client, reference, data, parts_sent=3)

    # Neuer Browser-Tab, gleiches Cookie: Teile abfragen, Rest hochladen, abschließen.
    url = sign(client, reference, body["masterId"], method="GET", key=body["key"],
               uploadId=upload_id).json()["url"]  # fmt: skip
    listed = client.get(url).content.decode()
    assert listed.count("<Part>") == 3

    earlier = [
        (int(n), e.replace("&quot;", ""))
        for n, e in re.findall(r"<PartNumber>(\d+)</PartNumber><ETag>(.*?)</ETag>", listed)
    ]
    rest = data[3 * 1024 :]
    later = send_parts(
        client, reference, body["masterId"], body["key"], upload_id, rest, 1024, first=4
    )
    complete(client, reference, body["masterId"], body["key"], upload_id, earlier + later)
    response = finish(client, reference, body["masterId"], hashlib.sha256(data).hexdigest())
    assert response.json()["state"] == "accepted"
    assert Master.objects.count() == 1


def test_fortsetzen_zaehlt_nicht_doppelt(client, reference, campaign):
    data = fits(width=100, height=100)
    campaign.quota = len(data)
    campaign.save()
    interrupted(client, reference, data)
    # Ein zweiter Start derselben Datei würde die Quote sprengen; Fortsetzen startet nicht neu.
    assert start(client, reference, size=len(data)).status_code == 400


# -- Zeitfenster ---------------------------------------------------------------


def test_nach_dem_ende_kein_neuer_upload(client, reference, campaign):
    ended(campaign, timedelta(minutes=1))
    response = start(client, reference, size=10)
    assert response.status_code == 400
    assert "beendet" in response.json()["error"]
    assert Master.objects.count() == 0


def test_vor_dem_beginn_kein_upload(client, reference, campaign):
    campaign.starts_at = timezone.now() + timedelta(days=1)
    campaign.save()
    assert start(client, reference, size=10).status_code == 400


def test_in_der_nachfrist_darf_ein_begonnener_upload_fertig_werden(client, reference, campaign):
    data = fits(width=100, height=100)
    body, upload_id = interrupted(client, reference, data, parts_sent=0)
    ended(campaign, timedelta(hours=5))  # in der Nachfrist
    parts = send_parts(client, reference, body["masterId"], body["key"], upload_id, data, 1024)
    complete(client, reference, body["masterId"], body["key"], upload_id, parts)
    response = finish(client, reference, body["masterId"], hashlib.sha256(data).hexdigest())
    assert response.json()["state"] == "accepted"


def test_nach_der_nachfrist_ist_alles_gesperrt(client, reference, campaign):
    data = fits(width=100, height=100)
    body, upload_id = interrupted(client, reference, data)
    ended(campaign, timedelta(hours=6, seconds=1))
    response = sign(client, reference, body["masterId"], method="PUT", key=body["key"],
                    uploadId=upload_id, partNumber=2)  # fmt: skip
    assert response.status_code == 400
    assert "schreibgeschützt" in response.json()["error"]
    response = finish(client, reference, body["masterId"], hashlib.sha256(data).hexdigest())
    assert response.status_code == 400
    assert Master.objects.get().state == Master.State.UPLOADING


def test_abbrechen_nach_der_nachfrist_gesperrt(client, reference, campaign):
    body, _ = interrupted(client, reference, fits(width=100, height=100))
    ended(campaign, timedelta(days=1))
    response = client.post(f"/abgabe/{reference}/master/{body['masterId']}/abbrechen/")
    assert response.status_code == 400
    assert Master.objects.get().state == Master.State.UPLOADING


def test_abbrechen_in_der_nachfrist_erlaubt(client, reference, campaign):
    body, _ = interrupted(client, reference, fits(width=100, height=100))
    ended(campaign, timedelta(hours=1))
    response = client.post(f"/abgabe/{reference}/master/{body['masterId']}/abbrechen/")
    assert response.json()["state"] == "aborted"


def test_abgabeseite_in_der_nachfrist(client, reference, campaign):
    interrupted(client, reference, fits(width=100, height=100))
    ended(campaign, timedelta(hours=1))
    content = page(client, reference)
    assert 'id="uploader"' in content  # zum Fortsetzen
    assert "Nachfrist" in content
    assert 'data-may-start="0"' in content


def test_abgabeseite_in_der_nachfrist_ohne_unterbrochene_uploads(client, reference, campaign):
    upload(client, reference, fits())
    ended(campaign, timedelta(hours=1))
    content = page(client, reference)
    assert 'id="uploader"' not in content
    assert "beendet" in content


def test_abgabeseite_nach_der_nachfrist_nur_ansehen(client, reference, campaign):
    upload(client, reference, fits(), filename="fertig.fits")
    interrupted(client, reference, fits(width=100, height=100))
    ended(campaign, timedelta(days=1))
    content = page(client, reference)
    assert "fertig.fits" in content  # Master weiter sichtbar
    assert 'id="uploader"' not in content  # keine Bedienelemente zum Ändern
    assert "data-upload-id=" not in content
    assert "schreibgeschützt" in content


def test_waehrend_der_aktion_darf_gestartet_werden(client, reference):
    assert 'data-may-start="1"' in page(client, reference)


# -- Uploader auf der Abgabeseite (Ticket #42) --------------------------------


def _own():
    return Submission.objects.get()


def test_uploader_waehrend_der_aktion(reference):
    assert may_start(_own())
    assert shows_uploader(_own())


def test_uploader_in_der_nachfrist_nur_zum_fortsetzen(client, reference, campaign):
    ended(campaign, timedelta(hours=1))
    assert not may_start(_own())
    assert not shows_uploader(_own())

    campaign.ends_at = timezone.now() + timedelta(hours=1)
    campaign.save()
    interrupted(client, reference, fits(width=100, height=100))
    ended(campaign, timedelta(hours=1))
    assert not may_start(_own())
    assert shows_uploader(_own())


def test_kein_uploader_nach_der_nachfrist_oder_nach_dem_rueckzug(client, reference, campaign):
    interrupted(client, reference, fits(width=100, height=100))
    ended(campaign, timedelta(hours=7))
    assert not shows_uploader(_own())

    campaign.ends_at = timezone.now() + timedelta(hours=1)
    campaign.save()
    services.withdraw(_own(), by=Submission.WithdrawnBy.PARTICIPANT)
    assert not shows_uploader(_own())
