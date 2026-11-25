"""Namensnennung nachträglich erlauben, auch nach einem Widerruf (Ticket #69)."""

import json
from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from files import fits
from uploads_helper import Participant

from submissions.models import Consent, Phase, Submission

pytestmark = pytest.mark.django_db


def grant_url(participant):
    return f"/submission/{participant.reference}/namensnennung/erlauben/"


def revoke_url(participant):
    return f"/submission/{participant.reference}/namensnennung/widerrufen/"


def grant(participant, name="Ada Sternguck", consent="on"):
    data = {"credit_name": name}
    if consent:
        data["consent_publish_credit"] = consent
    return participant.client.post(grant_url(participant), data)


def credit_consents(participant):
    return list(
        Consent.objects.filter(
            submission=participant.submission, kind=Consent.Kind.PUBLISH_CREDIT
        ).order_by("granted_at", "pk")
    )


def current(participant):
    return Submission.objects.get(pk=participant.submission.pk)


@pytest.fixture
def anonymous(campaign, valid_form, storage_dir):
    form = {k: v for k, v in valid_form.items() if k not in ("consent_publish_credit",)}
    del form["credit_name"]
    return Participant(form)


# -- erstmaliges Erlauben --------------------------------------------------------


def test_anonym_angelegt_erlaubt_die_namensnennung_nachtraeglich(anonymous, settings):
    assert f'href="{grant_url(anonymous)}"' in anonymous.page()

    response = grant(anonymous)
    assert response.status_code == 302
    assert response["Location"] == f"/submission/{anonymous.reference}/"

    (consent,) = credit_consents(anonymous)
    assert consent.revoked_at is None
    assert consent.text_version == settings.CONSENT_TEXT_VERSION
    assert current(anonymous).credit_name == "Ada Sternguck"
    assert current(anonymous).publishes_credit
    page = anonymous.page()
    assert "Ada Sternguck" in page
    assert grant_url(anonymous) not in page
    assert revoke_url(anonymous) in page


def test_erlauben_fragt_ausdruecklich_mit_haekchen_und_verweist_auf_den_hinweis(
    anonymous, settings
):
    response = anonymous.client.get(grant_url(anonymous))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'name="consent_publish_credit"' in content
    assert 'name="credit_name"' in content
    assert f"/datenschutz/{settings.CONSENT_TEXT_VERSION}/" in content
    assert credit_consents(anonymous) == []


def test_ohne_haekchen_wird_nichts_erlaubt(anonymous):
    response = grant(anonymous, consent="")
    assert response.status_code == 200
    assert "consent_publish_credit" in response.context["form"].errors
    assert credit_consents(anonymous) == []
    assert current(anonymous).credit_name == ""


@pytest.mark.parametrize("name", ["", "   "])
def test_der_name_ist_pflicht(anonymous, name):
    response = grant(anonymous, name=name)
    assert response.status_code == 200
    assert "credit_name" in response.context["form"].errors
    assert credit_consents(anonymous) == []
    assert current(anonymous).credit_name == ""


def test_erlauben_schreibt_die_begleitdateien_mit_dem_namen(anonymous, storage_dir):
    master = anonymous.upload(fits())
    sidecar = storage_dir / "objects" / master.sidecar_key
    assert json.loads(sidecar.read_bytes())["credit_name"] is None
    grant(anonymous)
    assert json.loads(sidecar.read_bytes())["credit_name"] == "Ada Sternguck"


def test_erlauben_steht_im_protokoll(anonymous):
    from django.contrib.admin.models import LogEntry

    grant(anonymous)
    message = LogEntry.objects.get(object_id=str(anonymous.submission.pk)).change_message
    assert "Namensnennung erlaubt" in message


# -- erneutes Erlauben nach einem Widerruf -----------------------------------------


def test_nach_dem_widerruf_erlaubt_eine_neue_einwilligung_die_widerrufene_bleibt(
    participant, settings
):
    settings.CONSENT_TEXT_VERSION = "2026-11-25"
    first = credit_consents(participant)[0]
    participant.client.post(revoke_url(participant))
    assert f'href="{grant_url(participant)}"' in participant.page()

    settings.CONSENT_TEXT_VERSION = "2026-12-01"
    grant(participant, name="Ada S.")

    old, new = credit_consents(participant)
    assert old.pk == first.pk
    assert old.revoked_at is not None
    assert old.text_version == "2026-11-25"
    assert new.pk != old.pk
    assert new.revoked_at is None
    assert new.granted_at > old.granted_at
    assert new.text_version == "2026-12-01"
    assert current(participant).credit_name == "Ada S."
    assert current(participant).publishes_credit
    assert "Ada S." in participant.page()


def test_wieder_erlauben_und_wieder_widerrufen_geht_beliebig_oft(participant):
    for round_ in range(3):
        participant.client.post(revoke_url(participant))
        grant(participant, name=f"Ada {round_}")
    consents = credit_consents(participant)
    assert len(consents) == 4
    assert [c.revoked_at is None for c in consents] == [False, False, False, True]
    assert current(participant).credit_name == "Ada 2"


def test_mit_gueltiger_einwilligung_gibt_es_nichts_zu_erlauben(participant):
    assert grant_url(participant) not in participant.page()
    response = participant.client.get(grant_url(participant))
    assert response.status_code == 302
    grant(participant, name="Anderer Name")
    assert len(credit_consents(participant)) == 1
    assert current(participant).credit_name == "Ada Sternguck"


def test_gleichzeitiges_erlauben_legt_nur_eine_gueltige_an(anonymous):
    """Zweiter Tab: Die Einwilligung gibt es schon, der zweite Aufruf ändert nichts."""
    from submissions import services

    first = services.grant_credit(anonymous.submission, "Ada Sternguck")
    assert first is not None
    assert services.grant_credit(anonymous.submission, "Zweiter Tab") is None
    assert len(credit_consents(anonymous)) == 1
    assert current(anonymous).credit_name == "Ada Sternguck"


def test_je_zweck_hoechstens_eine_nicht_widerrufene_einwilligung(participant):
    submission = participant.submission
    with pytest.raises(IntegrityError), transaction.atomic():
        Consent.objects.create(
            submission=submission, kind=Consent.Kind.PUBLISH_CREDIT, text_version="x"
        )
    Consent.objects.filter(submission=submission, kind=Consent.Kind.PUBLISH_CREDIT).update(
        revoked_at=timezone.now()
    )
    for _ in range(2):  # widerrufene dürfen sich häufen, eine gültige daneben
        Consent.objects.create(
            submission=submission,
            kind=Consent.Kind.PUBLISH_CREDIT,
            text_version="x",
            revoked_at=timezone.now(),
        )
    Consent.objects.create(
        submission=submission, kind=Consent.Kind.PUBLISH_CREDIT, text_version="x"
    )
    assert submission.consents.filter(kind=Consent.Kind.PUBLISH_CREDIT).count() == 4


# -- Phasen und Löschung -------------------------------------------------------------


@pytest.mark.parametrize(
    "starts, ends, phase",
    [
        (timedelta(days=1), timedelta(days=30), Phase.BEFORE),
        (-timedelta(days=2), -timedelta(minutes=1), Phase.GRACE),
        (-timedelta(days=30), -timedelta(days=5), Phase.CLOSED),
    ],
    ids=["vor-beginn", "nachfrist", "schreibgeschuetzt"],
)
def test_ausserhalb_der_laufenden_aktion_laesst_sich_nichts_erlauben(
    anonymous, campaign, starts, ends, phase
):
    now = timezone.now()
    campaign.starts_at = now + starts
    campaign.ends_at = now + ends
    campaign.save()
    assert campaign.phase() is phase

    assert grant_url(anonymous) not in anonymous.page()
    for response in (anonymous.client.get(grant_url(anonymous)), grant(anonymous)):
        assert response.status_code == 302
        assert response["Location"] == f"/submission/{anonymous.reference}/"
    assert credit_consents(anonymous) == []
    assert current(anonymous).credit_name == ""


def test_waehrend_der_laufenden_aktion_laesst_sich_erlauben(anonymous, campaign):
    assert campaign.phase() is Phase.OPEN
    assert anonymous.client.get(grant_url(anonymous)).status_code == 200
    assert grant(anonymous).status_code == 302
    assert len(credit_consents(anonymous)) == 1


def test_nach_dem_ende_der_aktion_bleibt_der_widerruf_moeglich_das_erlauben_nicht(
    participant, campaign
):
    campaign.ends_at = timezone.now() - timedelta(days=5)
    campaign.starts_at = campaign.ends_at - timedelta(days=10)
    campaign.save()
    participant.client.post(revoke_url(participant))
    assert grant(participant).status_code == 302
    assert current(participant).credit_name == ""
    (old,) = credit_consents(participant)
    assert old.revoked_at is not None


def test_nach_der_loeschung_ist_erlauben_nicht_mehr_moeglich(anonymous):
    anonymous.client.post(f"/submission/{anonymous.reference}/loeschen/")
    assert grant_url(anonymous) not in anonymous.page()
    for method in (anonymous.client.get, anonymous.client.post):
        response = method(grant_url(anonymous))
        assert response.status_code == 302
        assert response["Location"] == f"/submission/{anonymous.reference}/"
    assert not Consent.objects.filter(submission=anonymous.submission).exists()
    assert current(anonymous).credit_name == ""


def test_loeschung_in_einem_anderen_tab_waehrend_des_erlaubens_aendert_nichts(anonymous):
    from submissions import services

    submission = anonymous.submission
    anonymous.client.post(f"/submission/{anonymous.reference}/loeschen/")
    with pytest.raises(services.CreditNotAllowed):
        services.grant_credit(submission, "Ada Sternguck")
    assert not Consent.objects.filter(submission=submission).exists()


def test_fremde_submission_laesst_sich_nicht_erlauben(anonymous, another):
    stranger = another()
    assert stranger.client.get(grant_url(anonymous)).status_code == 404
    assert stranger.client.post(grant_url(anonymous), {"credit_name": "X"}).status_code == 404
    assert credit_consents(anonymous) == []


# -- Stellen, die Einwilligungen je Art annehmen: Manifest und Admin ---------------------


def manifest_entry(operator_client, campaign, participant):
    from admin_helper import ADMIN

    url = f"{ADMIN}submissions/campaign/{campaign.pk}/export/manifest.json"
    response = operator_client.get(url)
    assert response.status_code == 200, response.content
    return {s["reference"]: s for s in response.json()["submissions"]}[participant.reference]


def test_manifest_fuehrt_widerrufene_und_neue_einwilligung_je_mit_eigenem_zeitpunkt(
    operator_client, participant, campaign, settings
):
    settings.CONSENT_TEXT_VERSION = "2026-11-25"
    participant.client.post(revoke_url(participant))
    settings.CONSENT_TEXT_VERSION = "2026-12-01"
    grant(participant, name="Ada S.")

    entry = manifest_entry(operator_client, campaign, participant)
    credits = [c for c in entry["consents"] if c["kind"] == "publish_credit"]
    assert [c["text_version"] for c in credits] == ["2026-11-25", "2026-12-01"]
    assert credits[0]["revoked_at"] is not None
    assert credits[1]["revoked_at"] is None
    assert credits[0]["granted_at"] <= credits[1]["granted_at"]
    assert entry["credit_name"] == "Ada S."


def test_manifest_ohne_namen_solange_nur_eine_widerrufene_einwilligung_steht(
    operator_client, participant, campaign
):
    participant.client.post(revoke_url(participant))
    entry = manifest_entry(operator_client, campaign, participant)
    assert entry["credit_name"] is None
    credits = [c for c in entry["consents"] if c["kind"] == "publish_credit"]
    assert [c["revoked_at"] is not None for c in credits] == [True]


def test_admin_zeigt_beide_einwilligungen_und_nur_die_gueltige_laesst_sich_widerrufen(
    operator_client, participant
):
    from admin_helper import submission_url

    participant.client.post(revoke_url(participant))
    grant(participant, name="Ada S.")
    old, new = credit_consents(participant)

    response = operator_client.get(submission_url(participant.submission))
    page = response.content.decode()
    assert f"einwilligung/{new.pk}/widerrufen/" in page
    assert f"einwilligung/{old.pk}/widerrufen/" not in page
    (inline,) = (i for i in response.context["inline_admin_formsets"] if i.opts.model is Consent)
    rows = [(f.instance.kind, f.instance.pk) for f in inline.formset.forms if f.instance.pk]
    assert rows == [
        ("project_use", participant.submission.consents.get(kind="project_use").pk),
        ("publish_credit", old.pk),
        ("publish_credit", new.pk),
    ]
    assert "Ada S." in page
    # Betreiber erteilen keine Einwilligung.
    assert operator_client.post(grant_url(participant)).status_code in (302, 403, 404)


def test_betreiber_widerruft_die_neue_einwilligung_und_die_namensnennung_ist_weg(
    operator_client, participant
):
    from admin_helper import submission_url

    participant.client.post(revoke_url(participant))
    grant(participant, name="Ada S.")
    _, new = credit_consents(participant)
    url = submission_url(participant.submission, f"einwilligung/{new.pk}/widerrufen/")
    operator_client.post(url)
    assert current(participant).credit_name == ""
    assert not current(participant).publishes_credit
    assert [c.revoked_at is not None for c in credit_consents(participant)] == [True, True]
