"""Löschfrist: automatische Löschung 30 Tage nach dem endgültigen Export (Ticket #34)."""

from datetime import timedelta

import pytest
from admin_helper import submission_url
from django.contrib.admin.models import LogEntry
from django.core.management import call_command
from django.utils import timezone
from files import fits

from schwarmstack.models import LoginAttempt
from storage import BACKUP_PREFIX, get_storage
from submissions.models import Campaign, Consent, Master, Submission

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def recipients(settings):
    settings.OPERATOR_EMAILS = ["betrieb@example.org"]


def exported(campaign, days_ago):
    campaign.starts_at = timezone.now() - timedelta(days=90)
    campaign.ends_at = timezone.now() - timedelta(days=days_ago + 1)
    campaign.exported_at = timezone.now() - timedelta(days=days_ago)
    campaign.save()
    return campaign


@pytest.fixture
def stored(participant, storage_dir):
    """Eine Abgabe mit Master und Begleitdatei im Speicher, dazu eine Sicherung."""
    master = participant.upload(fits())
    get_storage().put_json(f"{BACKUP_PREFIX}db-2026-12-01.json", {"sicherung": True})
    return master


def keys():
    return sorted(get_storage().keys())


def run():
    call_command("delete_after_export")


def test_ohne_endgueltigen_export_tut_der_befehl_nichts(campaign, stored, mailoutbox):
    before = keys()
    run()
    assert keys() == before
    assert Master.objects.count() == 1
    assert mailoutbox == []


def test_vor_ablauf_der_loeschfrist_wird_nichts_geloescht(campaign, stored, mailoutbox):
    exported(campaign, days_ago=10)
    before = keys()
    run()
    assert keys() == before
    assert Submission.objects.count() == 1
    assert mailoutbox == []


def test_sieben_tage_vorher_kommt_genau_eine_erinnerung(campaign, stored, mailoutbox):
    exported(campaign, days_ago=23)
    run()
    run()
    assert len(mailoutbox) == 1
    assert "Löschung" in mailoutbox[0].subject
    assert Submission.objects.count() == 1
    assert Campaign.objects.get().deletion_warned_at is not None


def test_nach_ablauf_wird_alles_ausser_den_sicherungen_geloescht(
    campaign, stored, mailoutbox, operator_client
):
    # Ein Eingriff im Admin hinterlässt Kennung und Dateiname im Protokoll.
    operator_client.post(submission_url(stored.submission, "zurueckziehen/"))
    assert LogEntry.objects.exists()
    LoginAttempt.objects.create(ip_hash="a" * 64)
    exported(campaign, days_ago=31)
    run()

    assert keys() == [f"{BACKUP_PREFIX}db-2026-12-01.json"]
    assert Submission.objects.count() == 0
    assert Master.objects.count() == 0
    assert Consent.objects.count() == 0
    assert LoginAttempt.objects.count() == 0
    # Das Protokoll nennt Kennungen und Dateinamen; es wird mit gelöscht, bis auf die Einträge
    # zur Aktion (Export, Links), die keine Angaben von Teilnehmenden enthalten.
    assert not LogEntry.objects.exclude(content_type__model="campaign").exists()
    assert Campaign.objects.get().deleted_at is not None
    assert any("gelöscht" in mail.subject for mail in mailoutbox)


def test_loeschung_ist_idempotent(campaign, stored, mailoutbox):
    exported(campaign, days_ago=31)
    run()
    count = len(mailoutbox)
    deleted_at = Campaign.objects.get().deleted_at
    run()
    assert len(mailoutbox) == count
    assert Campaign.objects.get().deleted_at == deleted_at
