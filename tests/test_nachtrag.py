"""Schreibschutz nach dem endgültigen Export und Nachträge (Ticket #34)."""

from datetime import timedelta

import pytest
from admin_helper import ADMIN, change_form_data, log_messages, master_url, submission_url
from django.utils import timezone
from files import fits

from submissions.models import Campaign, Consent, Master, Submission

pytestmark = pytest.mark.django_db


@pytest.fixture
def exported(campaign):
    """Die Aktion ist beendet und endgültig exportiert."""
    campaign.starts_at = timezone.now() - timedelta(days=60)
    campaign.ends_at = timezone.now() - timedelta(days=10)
    campaign.exported_at = timezone.now() - timedelta(days=2)
    campaign.save()
    return campaign


@pytest.fixture
def uploaded(participant, campaign):
    """Eine Submission mit einem Master, hochgeladen vor dem Export."""
    return participant.upload(fits())


# -- Schreibschutz für Betreiber ---------------------------------------------------


def test_nach_dem_export_keine_aenderung_von_namensnennung_und_setup(
    operator_client, participant, uploaded, exported
):
    url = submission_url(participant.submission)
    data = change_form_data(operator_client.get(url), setup_description="geändert")
    data["credit_name"] = "Neuer Name"
    operator_client.post(url, data)
    submission = Submission.objects.get(pk=participant.submission.pk)
    assert submission.setup_description == "RedCat 51, ASI2600MM"
    assert submission.credit_name == "Ada Sternguck"


def test_nach_dem_export_kein_master_loeschen(operator_client, uploaded, exported):
    assert operator_client.get(master_url(uploaded, "loeschen")).status_code == 404
    assert operator_client.post(master_url(uploaded, "loeschen")).status_code == 404
    assert Master.objects.filter(pk=uploaded.pk).exists()


def test_nach_dem_export_keine_aenderung_an_der_aktion(operator_client, exported):
    url = f"{ADMIN}submissions/campaign/{exported.pk}/change/"
    form = operator_client.get(url).context["adminform"].form
    assert set(form.fields) == set()


def test_vor_dem_export_bleibt_aendern_moeglich(operator_client, participant, uploaded):
    url = submission_url(participant.submission)
    data = change_form_data(operator_client.get(url), setup_description="geändert")
    operator_client.post(url, data)
    assert Submission.objects.get(pk=participant.submission.pk).setup_description == "geändert"


# -- Nachtrag: Löschung und Widerruf bleiben möglich --------------------------------


def test_loeschung_nach_dem_export_ist_ein_nachtrag(
    operator_client, participant, uploaded, exported, mailoutbox, settings
):
    settings.OPERATOR_EMAILS = ["betrieb@example.org"]
    operator_client.post(submission_url(participant.submission, "loeschen/"))

    submission = Submission.objects.get(pk=participant.submission.pk)
    assert submission.is_deleted
    assert submission.amended_at is not None
    assert not Master.objects.filter(submission=submission).exists()
    assert len(mailoutbox) == 1
    mail = mailoutbox[0]
    assert mail.to == ["betrieb@example.org"]
    assert participant.reference in mail.subject + mail.body
    # Meldungen enthalten nur die Submission-ID, keine Angaben (ADR 0007).
    assert "Ada" not in mail.subject + mail.body
    assert "RedCat" not in mail.subject + mail.body


def test_widerruf_der_namensnennung_nach_dem_export_ist_ein_nachtrag(
    operator_client, participant, uploaded, exported, mailoutbox, settings
):
    settings.OPERATOR_EMAILS = ["betrieb@example.org"]
    consent = participant.submission.consents.get(kind=Consent.Kind.PUBLISH_CREDIT)
    operator_client.post(
        submission_url(participant.submission, f"einwilligung/{consent.pk}/widerrufen/")
    )

    submission = Submission.objects.get(pk=participant.submission.pk)
    assert submission.amended_at is not None
    assert submission.credit_name == ""
    assert len(mailoutbox) == 1
    assert "Ada" not in mailoutbox[0].body


def test_nachtrag_im_admin_und_im_manifest(operator_client, participant, uploaded, exported):
    consent = participant.submission.consents.get(kind=Consent.Kind.PUBLISH_CREDIT)
    operator_client.post(
        submission_url(participant.submission, f"einwilligung/{consent.pk}/widerrufen/")
    )
    export = f"{ADMIN}submissions/campaign/{exported.pk}/export/"
    assert participant.reference in operator_client.get(export).content.decode()
    listing = operator_client.get(f"{ADMIN}submissions/submission/?nachtrag=ja")
    assert participant.reference in listing.content.decode()

    data = operator_client.get(export + "manifest.json").json()
    entry = next(s for s in data["submissions"] if s["reference"] == participant.reference)
    assert entry["amended_at"] is not None
    assert entry["credit_name"] is None


def test_vor_dem_export_ist_eine_loeschung_kein_nachtrag(
    operator_client, participant, uploaded, mailoutbox
):
    operator_client.post(submission_url(participant.submission, "loeschen/"))
    assert Submission.objects.get(pk=participant.submission.pk).amended_at is None
    assert mailoutbox == []
    assert Campaign.objects.get().exported_at is None
    assert "Submission gelöscht" in log_messages(participant.submission)


def test_nach_dem_export_belichtungsangaben_nur_noch_ansehen(operator_client, uploaded, exported):
    url = f"{ADMIN}submissions/master/{uploaded.pk}/change/"
    response = operator_client.get(url)
    assert response.status_code == 200
    assert not response.context["has_change_permission"]
    operator_client.post(url, {"telescope": "geändert"})
    uploaded.refresh_from_db()
    assert uploaded.telescope != "geändert"


def test_foto_loeschen_nach_dem_export_ist_ein_nachtrag(
    operator_client, participant, uploaded, exported, mailoutbox, settings
):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from photo_files import foto

    settings.OPERATOR_EMAILS = ["betrieb@example.org"]
    # Das Foto kam vor dem Export dazu.
    exported.exported_at = None
    exported.ends_at = timezone.now() + timedelta(days=1)
    exported.save()
    upload = SimpleUploadedFile("Garten.jpg", foto("jpeg"), content_type="image/jpeg")
    participant.client.post(
        f"/submission/{participant.reference}/aendern/foto/",
        {"equipment_photo": upload, "consent_equipment_photo": "on"},
    )
    exported.ends_at = timezone.now() - timedelta(days=10)
    exported.exported_at = timezone.now() - timedelta(days=2)
    exported.save()

    operator_client.post(submission_url(participant.submission, "foto/loeschen/"))
    submission = Submission.objects.get(pk=participant.submission.pk)
    assert submission.photo is None
    assert submission.amended_at is not None
    assert len(mailoutbox) == 1
    assert "Equipment-Foto" in mailoutbox[0].body
