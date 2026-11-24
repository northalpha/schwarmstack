"""Die Aktion ist genau ein Datensatz (Ticket #9, ADR 0004)."""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError

from submissions.models import Campaign, Master, Submission

pytestmark = pytest.mark.django_db


def test_nachfrist_standard_sechs_stunden(campaign):
    assert campaign.grace_period == timedelta(hours=6)


def test_nur_eine_aktion(campaign):
    with pytest.raises(IntegrityError):
        Campaign.objects.create(
            object_name="M 31",
            starts_at=campaign.starts_at,
            ends_at=campaign.ends_at,
            quota=1,
            global_cap=1,
        )


def test_current_liefert_die_aktion(campaign):
    assert Campaign.current() == campaign


def test_current_ohne_aktion(db):
    assert Campaign.current() is None


def test_befehl_legt_aktion_an_und_aendert_sie(db):
    args = [
        "--object", "M 101",
        "--starts-at", "2027-03-01T00:00+01:00",
        "--ends-at", "2027-04-30T23:59+02:00",
        "--quota-gib", "2",
        "--global-cap-gib", "400",
    ]  # fmt: skip
    call_command("campaign", *args)
    campaign = Campaign.current()
    assert campaign.object_name == "M 101"
    assert campaign.quota == 2 * 1024**3
    assert campaign.global_cap == 400 * 1024**3
    assert campaign.grace_period == timedelta(hours=6)

    call_command("campaign", *args[:-2], "--global-cap-gib", "500", "--grace-hours", "3")
    assert Campaign.objects.count() == 1
    campaign = Campaign.current()
    assert campaign.global_cap == 500 * 1024**3
    assert campaign.grace_period == timedelta(hours=3)


def test_ende_muss_nach_dem_beginn_liegen(campaign):
    campaign.ends_at = campaign.starts_at
    with pytest.raises(ValidationError) as exc:
        campaign.full_clean()
    assert "ends_at" in exc.value.message_dict


def test_befehl_lehnt_ende_vor_dem_beginn_ab(db):
    with pytest.raises(CommandError, match="nach dem Beginn"):
        call_command(
            "campaign",
            "--object", "M 101",
            "--starts-at", "2027-03-01T00:00+01:00",
            "--ends-at", "2027-03-01T00:00+01:00",
            "--quota-gib", "2",
            "--global-cap-gib", "400",
        )  # fmt: skip
    assert Campaign.current() is None


def test_befehl_lehnt_gesamtgrenze_unter_der_belegung_ab(campaign, reference):
    """Wie im Admin: uploads.check_global_cap (Ticket #42)."""
    Master.objects.create(
        submission=Submission.objects.get(), key="k", declared_size=3 * 1024**2, original_name="a"
    )
    with pytest.raises(CommandError, match="Belegung"):
        call_command(
            "campaign",
            "--object", "M 101",
            "--starts-at", campaign.starts_at.isoformat(),
            "--ends-at", campaign.ends_at.isoformat(),
            "--quota-gib", "2",
            "--global-cap-gib", "0.001",
        )  # fmt: skip
    campaign.refresh_from_db()
    assert campaign.global_cap == 400 * 1024**3
