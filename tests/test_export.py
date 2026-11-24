"""Export und Manifest für die Betreiber (Ticket #34)."""

from datetime import timedelta

import pytest
from admin_helper import ADMIN, log_messages
from django.utils import timezone
from files import fits, xisf

from submissions.models import Campaign, Consent, Submission

pytestmark = pytest.mark.django_db


def export_url(campaign, suffix=""):
    return f"{ADMIN}submissions/campaign/{campaign.pk}/export/{suffix}"


def manifest(client, campaign):
    response = client.get(export_url(campaign, "manifest.json"))
    assert response.status_code == 200, response.content
    assert response["Content-Disposition"].startswith("attachment")
    return response.json()


def closed(campaign, ago=timedelta(days=1)):
    """Die Aktion ist seit `ago` beendet, samt Nachfrist."""
    campaign.starts_at = timezone.now() - timedelta(days=60)
    campaign.ends_at = timezone.now() - campaign.grace_period - ago
    campaign.save()
    return campaign


def by_reference(data):
    return {s["reference"]: s for s in data["submissions"]}


# -- vorläufiger Export ---------------------------------------------------------


def test_vorlaeufiger_export_enthaelt_abgaben_und_master_ohne_links(
    operator_client, participant, campaign
):
    master = participant.upload(fits(), channel="Ha", filename="m101_ha.fits")
    data = manifest(operator_client, campaign)

    assert data["final"] is False
    assert data["campaign"]["object_name"] == "M 101"
    entry = by_reference(data)[participant.reference]
    assert entry["credit_name"] == "Ada Sternguck"
    assert entry["setup_description"] == "RedCat 51, ASI2600MM"
    assert entry["created_at"]
    assert [m["master_id"] for m in entry["masters"]] == [master.public_id.hex]
    exported = entry["masters"][0]
    assert exported["channel"] == "Ha"
    assert exported["original_name"] == "m101_ha.fits"
    assert exported["size"] == len(fits())
    assert exported["sha256"] == master.sha256
    assert exported["duplicate_of"] is None
    assert exported["path"] == f"{participant.reference}/Ha_{master.public_id.hex[:8]}.fits"
    assert "url" not in exported
    assert any("Vorläufiger Export" in m for m in log_messages())


def test_manifest_enthaelt_alle_einwilligungen_mit_textversion_und_widerruf(
    operator_client, participant, campaign, settings
):
    publish = participant.submission.consents.get(kind=Consent.Kind.PUBLISH_CREDIT)
    publish.revoked_at = timezone.now()
    publish.save()
    entry = by_reference(manifest(operator_client, campaign))[participant.reference]

    consents = {c["kind"]: c for c in entry["consents"]}
    assert set(consents) == {"project_use", "publish_credit"}
    assert consents["project_use"]["text_version"] == settings.CONSENT_TEXT_VERSION
    assert consents["project_use"]["granted_at"]
    assert consents["project_use"]["revoked_at"] is None
    assert consents["publish_credit"]["revoked_at"] is not None
    # Ohne gültige Einwilligung keine Nennung im Manifest.
    assert entry["credit_name"] is None


def test_anonyme_abgabe_hat_keine_nennung(operator_client, another, valid_form, campaign):
    from uploads_helper import Participant

    anonymous = Participant({**valid_form, "consent_publish_credit": ""})
    entry = by_reference(manifest(operator_client, campaign))[anonymous.reference]
    assert entry["credit_name"] is None
    assert [c["kind"] for c in entry["consents"]] == ["project_use"]


def test_manifest_nur_mit_angenommenen_mastern_und_dublettenverweis(
    operator_client, participant, another, campaign
):
    original = participant.upload(xisf(), filename="m101_L.xisf")
    participant.upload(fits(bitpix=16))  # abgelehnt
    second = another()
    duplicate = second.upload(xisf(), filename="m101_L.xisf")
    data = by_reference(manifest(operator_client, campaign))

    assert [m["master_id"] for m in data[participant.reference]["masters"]] == [
        original.public_id.hex
    ]
    assert data[second.reference]["masters"][0]["duplicate_of"] == {
        "reference": participant.reference,
        "master_id": original.public_id.hex,
    }
    assert duplicate.duplicate_of_id == original.pk


def test_zurueckgezogene_abgabe_nur_mit_kennung_und_zeitpunkt(
    operator_client, participant, campaign
):
    participant.upload(fits())
    from submissions import services

    services.withdraw(participant.submission, by=Submission.WithdrawnBy.PARTICIPANT)
    entry = by_reference(manifest(operator_client, campaign))[participant.reference]
    assert entry.keys() == {"reference", "withdrawn_at", "amended_at"}
    assert entry["withdrawn_at"]
    assert entry["amended_at"] is None


def test_vorlaeufiger_export_hat_keine_download_liste(operator_client, campaign):
    assert operator_client.get(export_url(campaign, "download-liste.txt")).status_code == 404


def test_export_nur_fuer_betreiber(client, campaign):
    response = client.get(export_url(campaign, "manifest.json"))
    assert response.status_code == 302
    assert "/login/" in response["Location"]


def test_exportseite_zeigt_den_stand(operator_client, campaign):
    response = operator_client.get(export_url(campaign))
    assert response.status_code == 200
    page = response.content.decode()
    assert "Vorläufiger Export" in page
    assert Campaign.objects.get().exported_at is None


# -- endgültiger Export ---------------------------------------------------------


def finalize(client, campaign):
    return client.post(export_url(campaign, "endgueltig/"))


def test_endgueltiger_export_nicht_vor_ende_plus_nachfrist(operator_client, campaign):
    campaign.ends_at = timezone.now() - timedelta(hours=1)  # noch in der Nachfrist
    campaign.save()
    response = finalize(operator_client, campaign)
    assert response.status_code == 302
    assert Campaign.objects.get().exported_at is None


def test_endgueltiger_export_fragt_erst_nach(operator_client, campaign):
    closed(campaign)
    response = operator_client.get(export_url(campaign, "endgueltig/"))
    assert response.status_code == 200
    assert "genau einmal" in response.content.decode()
    assert Campaign.objects.get().exported_at is None


def test_endgueltiger_export_genau_einmal(operator_client, campaign):
    closed(campaign)
    finalize(operator_client, campaign)
    first = Campaign.objects.get().exported_at
    assert first is not None
    finalize(operator_client, campaign)
    assert Campaign.objects.get().exported_at == first
    assert log_messages(campaign).count("Endgültiger Export ausgelöst") == 1


def test_nach_dem_endgueltigen_export_manifest_mit_links_und_download_liste(
    operator_client, participant, campaign
):
    master = participant.upload(fits(), channel="R")
    closed(campaign)
    finalize(operator_client, campaign)

    data = manifest(operator_client, campaign)
    assert data["final"] is True
    assert data["campaign"]["deletes_at"]
    exported = by_reference(data)[participant.reference]["masters"][0]
    # Der Link liefert genau diesen Master.
    response = operator_client.get(exported["url"])
    assert response.status_code == 200
    assert b"".join(response.streaming_content) == fits()

    listing = operator_client.get(export_url(campaign, "download-liste.txt"))
    assert listing.status_code == 200
    lines = listing.content.decode().splitlines()
    path = f"{participant.reference}/R_{master.public_id.hex[:8]}.fits"
    assert lines[1:] == [f"  out={path}", f"  checksum=sha-256={master.sha256}"]
    assert lines[0].startswith("/")
    issued = [m for m in log_messages(campaign) if "Links" in m]
    assert len(issued) == 2


def test_nach_ablauf_der_loeschfrist_keine_links_mehr(operator_client, participant, campaign):
    participant.upload(fits())
    closed(campaign, ago=timedelta(days=40))
    campaign.exported_at = timezone.now() - timedelta(days=31)
    campaign.save()
    assert operator_client.get(export_url(campaign, "download-liste.txt")).status_code == 404
    assert operator_client.get(export_url(campaign, "manifest.json")).status_code == 404


def test_exportseite_zeigt_die_restlichen_tage_der_loeschfrist(operator_client, campaign):
    closed(campaign, ago=timedelta(days=10))
    campaign.exported_at = timezone.now() - timedelta(days=5, hours=1)
    campaign.save()
    page = operator_client.get(export_url(campaign)).content.decode()
    assert "noch 25 Tage" in page


def test_statistik_zeigt_die_restlichen_tage_der_loeschfrist(operator_client, campaign):
    closed(campaign, ago=timedelta(days=10))
    campaign.exported_at = timezone.now() - timedelta(days=28)
    campaign.save()
    page = operator_client.get(ADMIN).content.decode()
    assert "Löschfrist: noch 2 Tage" in page
