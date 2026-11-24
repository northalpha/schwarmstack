"""Quote, Gesamtgrenze, Höchstgröße und Abbrechen (Ticket #15)."""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.test import Client
from django.utils import timezone
from files import fits
from uploads_helper import create, finish, send_parts, sign, start, upload

from submissions.models import Master, Submission
from submissions.uploads import STALE_AFTER, check_global_cap, submission_usage, usage

pytestmark = pytest.mark.django_db

MIB = 1024**2


@pytest.fixture
def storage_dir(settings, tmp_path):
    settings.STORAGE_LOCAL_DIR = tmp_path / "speicher"
    return settings.STORAGE_LOCAL_DIR


def abort(client, reference, master_id):
    return client.post(f"/submission/{reference}/master/{master_id}/abbrechen/")


def set_campaign(campaign, **values):
    for name, value in values.items():
        setattr(campaign, name, value)
    campaign.save()


# -- Höchstgröße je Master ---------------------------------------------------


def test_hoechstgroesse_standard_500_mib(campaign):
    assert campaign.max_master_size == 500 * MIB


def test_master_ueber_der_hoechstgroesse(client, reference):
    response = start(client, reference, size=500 * MIB + 1)
    assert response.status_code == 400
    assert "500" in response.json()["error"]
    assert Master.objects.count() == 0


def test_master_genau_auf_der_hoechstgroesse(client, reference):
    assert start(client, reference, size=500 * MIB).status_code == 201


# -- Quote je Submission ---------------------------------------------------------


def test_quote_wird_vor_dem_start_geprueft(client, reference, campaign):
    set_campaign(campaign, quota=100 * MIB)
    assert start(client, reference, size=60 * MIB).status_code == 201
    response = start(client, reference, size=50 * MIB)
    assert response.status_code == 400
    assert "Quote" in response.json()["error"]
    assert "40" in response.json()["error"]  # noch frei
    assert start(client, reference, size=40 * MIB).status_code == 201


def test_quote_gilt_je_submission(client, reference, campaign, valid_form):
    set_campaign(campaign, quota=100 * MIB)
    start(client, reference, size=100 * MIB)
    other = Client()
    other.post("/", valid_form)
    other_ref = Submission.objects.exclude(reference=reference).get().reference
    assert start(other, other_ref, size=100 * MIB).status_code == 201


def test_angenommene_master_zaehlen_mit_tatsaechlicher_groesse(client, reference, campaign):
    data = fits()
    set_campaign(campaign, quota=len(data) * 2)
    upload(client, reference, data)
    assert start(client, reference, size=len(data) + 1).status_code == 400
    assert start(client, reference, size=len(data)).status_code == 201


def test_abgelehnte_master_zaehlen_nicht(client, reference, campaign):
    bad = fits(bitpix=16)
    set_campaign(campaign, quota=len(bad))
    assert upload(client, reference, bad).json()["state"] == "rejected"
    assert start(client, reference, size=len(bad)).status_code == 201


# -- Gesamtgrenze ------------------------------------------------------------


def test_gesamtgrenze_ueber_alle_submissions(client, reference, campaign, valid_form):
    set_campaign(campaign, global_cap=150 * MIB)
    start(client, reference, size=100 * MIB)
    other = Client()
    other.post("/", valid_form)
    other_ref = Submission.objects.exclude(reference=reference).get().reference
    response = start(other, other_ref, size=60 * MIB)
    assert response.status_code == 400
    assert "Gesamtgrenze" in response.json()["error"]
    assert start(other, other_ref, size=50 * MIB).status_code == 201


def test_reservierung_zaehlt_schon_waehrend_des_uploads(client, reference, campaign):
    """Mehrere gleichzeitig gestartete Uploads überziehen die Grenzen nicht."""
    set_campaign(campaign, quota=100 * MIB, global_cap=100 * MIB)
    started = [start(client, reference, size=30 * MIB).status_code for _ in range(4)]
    assert started == [201, 201, 201, 400]


# -- Abbrechen ---------------------------------------------------------------


def test_abbrechen_gibt_reservierung_frei(client, reference, campaign, storage_dir):
    set_campaign(campaign, quota=100 * MIB)
    body = start(client, reference, size=100 * MIB).json()
    upload_id = create(client, body["url"])
    send_parts(client, reference, body["masterId"], body["key"], upload_id, b"x" * 2048)
    assert start(client, reference, size=1).status_code == 400

    response = abort(client, reference, body["masterId"])
    assert response.status_code == 200
    assert response.json()["state"] == "aborted"
    assert Master.objects.get().state == Master.State.ABORTED
    assert start(client, reference, size=100 * MIB).status_code == 201
    assert not any((storage_dir / "multipart").iterdir())  # Multipart im Speicher abgebrochen


def test_abbrechen_vor_dem_anlegen_des_multipart(client, reference):
    body = start(client, reference, size=10).json()
    assert abort(client, reference, body["masterId"]).json()["state"] == "aborted"


def test_abgebrochener_master_kann_nicht_mehr_fertig_werden(client, reference):
    body = start(client, reference, size=10).json()
    abort(client, reference, body["masterId"])
    assert sign(client, reference, body["masterId"], method="GET", key=body["key"],
                uploadId="u").status_code == 400  # fmt: skip
    assert finish(client, reference, body["masterId"]).json()["state"] == "aborted"


def test_angenommene_master_lassen_sich_nicht_abbrechen(client, reference):
    upload(client, reference, fits())
    master = Master.objects.get()
    response = abort(client, reference, str(master.public_id))
    assert response.status_code == 409
    assert Master.objects.get().state == Master.State.ACCEPTED


def test_abbrechen_fremder_master_gibt_404(client, reference, valid_form):
    body = start(client, reference, size=10).json()
    other = Client()
    other.post("/", valid_form)
    assert abort(other, reference, body["masterId"]).status_code == 404


# -- Aufgegebene Uploads -----------------------------------------------------


def test_aufgegebene_uploads_geben_nach_7_tagen_frei(client, reference, campaign):
    set_campaign(campaign, quota=100 * MIB)
    start(client, reference, size=100 * MIB)
    Master.objects.update(created_at=timezone.now() - timedelta(days=7, minutes=1))
    assert start(client, reference, size=100 * MIB).status_code == 201
    states = sorted(Master.objects.values_list("state", flat=True))
    assert states == ["aborted", "uploading"]


def test_juengere_uploads_bleiben_reserviert(client, reference, campaign):
    set_campaign(campaign, quota=100 * MIB)
    start(client, reference, size=100 * MIB)
    Master.objects.update(created_at=timezone.now() - timedelta(days=6, hours=23))
    assert start(client, reference, size=1).status_code == 400


# -- Anzeige -----------------------------------------------------------------


def test_submission_seite_zeigt_belegung(client, reference, campaign):
    set_campaign(campaign, quota=1000 * MIB)
    start(client, reference, size=250 * MIB)
    content = client.get(f"/submission/{reference}/").content.decode().replace("\xa0", " ")
    assert "250,0 MB" in content
    assert "1000,0 MB" in content or "1,0 GB" in content  # Django: 1000 MiB -> "1000,0 MB"
    assert 'value="25"' in content  # Balken in Prozent


def test_submission_seite_gibt_hoechstgroesse_an_den_uploader(client, reference):
    content = client.get(f"/submission/{reference}/").content.decode()
    assert f'data-max-size="{500 * MIB}"' in content


def test_abgebrochene_master_stehen_nicht_in_der_liste(client, reference):
    body = start(client, reference, size=10, filename="weg.fits").json()
    abort(client, reference, body["masterId"])
    assert "weg.fits" not in client.get(f"/submission/{reference}/").content.decode()


# -- Gesamtgrenze ändern und Belegung je Submission (Ticket #42) ------------------


def test_gesamtgrenze_nicht_unter_der_belegung(reference, campaign):
    Master.objects.create(
        submission=Submission.objects.get(), key="k", declared_size=3 * MIB, original_name="a"
    )
    with pytest.raises(ValidationError, match="Belegung"):
        check_global_cap(3 * MIB - 1)
    check_global_cap(3 * MIB)


def test_aufgegebene_uploads_zaehlen_beim_aendern_der_gesamtgrenze_nicht(reference, campaign):
    master = Master.objects.create(
        submission=Submission.objects.get(), key="k", declared_size=3 * MIB, original_name="a"
    )
    Master.objects.filter(pk=master.pk).update(created_at=timezone.now() - STALE_AFTER * 2)
    check_global_cap(0)


def test_belegung_je_submission_wie_fuer_die_quote(client, reference, campaign, storage_dir):
    upload(client, reference, fits())
    start(client, reference, size=5 * MIB)
    submission = Submission.objects.annotate(used=submission_usage()).get()
    assert submission.used == usage(submission.masters.all()) > 5 * MIB
