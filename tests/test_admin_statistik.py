"""Statistik als Startseite des Admin, bei einem bekannten Datenbestand (Ticket #29)."""

import datetime as dt
from zoneinfo import ZoneInfo

import pytest
from admin_helper import ADMIN, operator, operator_client, submission_url  # noqa: F401
from django.utils import timezone
from files import fits, xisf
from uploads_helper import new_submission, start, upload

from submissions.models import Master, Submission

pytestmark = pytest.mark.django_db

GIB = 1024**3
BERLIN = ZoneInfo("Europe/Berlin")
L_DATA = fits()
HA_DATA = xisf()


@pytest.fixture
def bestand(campaign, valid_form, settings, tmp_path, operator_client):  # noqa: F811
    """A: L + Hα angenommen. B: Dublette von A, zwei abgelehnt. C: ein Upload läuft.
    D: zurückgezogen. E: ein abgebrochener Upload."""
    settings.STORAGE_LOCAL_DIR = tmp_path
    a_client, a = new_submission(valid_form)
    upload(a_client, a.reference, L_DATA, channel="L")
    upload(a_client, a.reference, HA_DATA, channel="Ha", filename="ha.xisf")

    b_client, b = new_submission(valid_form)
    upload(b_client, b.reference, L_DATA, channel="L")
    upload(b_client, b.reference, fits(bitpix=16), channel="R", filename="r.fits")
    upload(b_client, b.reference, fits(), channel="RGB", filename="rgb.fits")

    c_client, c = new_submission(valid_form)
    start(c_client, c.reference, size=1000)

    d_client, d = new_submission(valid_form)
    upload(d_client, d.reference, fits(width=9), channel="B", filename="b.fits")
    operator_client.post(submission_url(d, "zurueckziehen/"))

    e_client, e = new_submission(valid_form)
    master_id = start(e_client, e.reference, size=2000).json()["masterId"]
    e_client.post(f"/abgabe/{e.reference}/master/{master_id}/abbrechen/")
    return {"a": a, "b": b, "c": c, "d": d, "e": e}


def statistik(client):
    response = client.get(ADMIN)
    assert response.status_code == 200
    return response, response.context["statistik"]


def test_abgaben_aktiv_und_zurueckgezogen(operator_client, bestand):  # noqa: F811
    _, s = statistik(operator_client)
    assert s.submissions_active == 4
    assert s.submissions_withdrawn == 1


def test_master_je_zustand(operator_client, bestand):  # noqa: F811
    _, s = statistik(operator_client)
    assert dict(s.masters_by_state) == {
        "im Upload": 1,
        "angenommen": 3,
        "abgelehnt": 2,
        "abgebrochen": 1,
    }


def test_angenommene_master_je_kanal(operator_client, bestand):  # noqa: F811
    _, s = statistik(operator_client)
    assert {c.label: (c.count, c.size) for c in s.channels} == {
        "L": (2, 2 * len(L_DATA)),
        "Hα": (1, len(HA_DATA)),
    }


def test_belegung_gegen_die_gesamtgrenze(operator_client, bestand):  # noqa: F811
    _, s = statistik(operator_client)
    assert s.accepted == 2 * len(L_DATA) + len(HA_DATA)
    assert s.reserved == 1000
    assert s.used == s.accepted + 1000
    assert s.global_cap == 400 * GIB


def test_dubletten(operator_client, bestand):  # noqa: F811
    _, s = statistik(operator_client)
    assert s.duplicates == 1


def test_ablehnungen_nach_kategorie_mit_link_zur_liste(operator_client, bestand):  # noqa: F811
    response, s = statistik(operator_client)
    counts = {r.label: r.count for r in s.rejections}
    assert counts["kein 32-Bit-Gleitkomma"] == 1
    assert counts["falsche Ebenen für den Kanal"] == 1
    assert counts["falsches Format"] == 0

    link = next(r.url for r in s.rejections if r.label == "kein 32-Bit-Gleitkomma")
    assert link in response.content.decode().replace("&amp;", "&")
    listed = operator_client.get(link).context["cl"].result_list
    assert [m.original_name for m in listed] == ["r.fits"]


def test_verlauf_je_tag_in_berliner_zeit(operator_client, bestand):  # noqa: F811
    # 23:30 UTC am 10. Januar ist in Berlin schon der 11.
    Submission.objects.filter(pk=bestand["e"].pk).update(
        created_at=dt.datetime(2025, 1, 10, 23, 30, tzinfo=dt.UTC)
    )
    Master.objects.filter(submission=bestand["a"], channel="Ha").update(
        completed_at=dt.datetime(2025, 1, 10, 23, 30, tzinfo=dt.UTC)
    )
    _, s = statistik(operator_client)
    days = {d.day: d for d in s.days}
    today = timezone.now().astimezone(BERLIN).date()

    earlier = days[dt.date(2025, 1, 11)]
    assert (earlier.new_submissions, earlier.accepted, earlier.withdrawals) == (
        1,
        len(HA_DATA),
        0,
    )
    # Zurückgezogene Abgaben fallen aus dem Verlauf heraus, ihr Rückzug steht daneben.
    assert (days[today].new_submissions, days[today].withdrawals) == (3, 1)
    assert days[today].accepted == 2 * len(L_DATA)


def test_ohne_aktion_trotzdem_erreichbar(operator_client, db):  # noqa: F811
    assert operator_client.get(ADMIN).status_code == 200
