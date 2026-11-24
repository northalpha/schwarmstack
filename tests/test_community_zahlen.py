"""Community-Zahlen: öffentliche Summen zur Aktion unter /zahlen.json (Ticket #53)."""

from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone
from files import fits
from uploads_helper import new_submission, start, upload

from submissions.models import Submission
from submissions.services import withdraw

pytestmark = pytest.mark.django_db

URL = "/zahlen.json"
L_DATA = fits()


@pytest.fixture(autouse=True)
def frischer_cache():
    from django.core.cache import cache

    cache.clear()


def zahlen(client=None, **headers):
    response = (client or Client()).get(URL, headers=headers)
    assert response.status_code == 200
    return response


def test_ohne_aktion_nullen():
    assert zahlen().json() == {"submissions": 0, "masters": 0, "bytes": 0}


@pytest.fixture
def bestand(campaign, valid_form, storage_dir):
    """A: L angenommen, R abgelehnt. B: Dublette von L aus A, ein Upload läuft.
    C: ohne Master. D: angenommen, dann zurückgezogen."""
    a_client, a = new_submission(valid_form)
    upload(a_client, a.reference, L_DATA, channel="L")
    upload(a_client, a.reference, fits(bitpix=16), channel="R", filename="r.fits")

    b_client, b = new_submission(valid_form)
    upload(b_client, b.reference, L_DATA, channel="L")
    start(b_client, b.reference, size=1000)

    new_submission(valid_form)

    d_client, d = new_submission(valid_form)
    upload(d_client, d.reference, fits(width=9), channel="B", filename="b.fits")
    withdraw(d, by=Submission.WithdrawnBy.PARTICIPANT)


def test_zaehlregeln(bestand):
    # A, B und C; D ist zurückgezogen. Master: L aus A und die Dublette aus B.
    assert zahlen().json() == {"submissions": 3, "masters": 2, "bytes": 2 * len(L_DATA)}


def test_vor_beginn_200(campaign):
    campaign.starts_at = timezone.now() + timedelta(days=1)
    campaign.save()
    assert zahlen().json() == {"submissions": 0, "masters": 0, "bytes": 0}


def test_nach_ende_bleiben_die_zahlen(bestand, campaign):
    campaign.starts_at = timezone.now() - timedelta(days=60)
    campaign.ends_at = timezone.now() - timedelta(days=30)
    campaign.save()
    assert zahlen().json() == {"submissions": 3, "masters": 2, "bytes": 2 * len(L_DATA)}


def test_ohne_cookie_mit_cache_control(settings):
    settings.COMMUNITY_CACHE_SECONDS = 25
    response = zahlen()
    assert "Set-Cookie" not in response
    assert not response.cookies
    assert response["Cache-Control"] == "public, max-age=25"


@pytest.mark.parametrize(
    ("origins", "origin", "allowed"),
    [
        (["https://community.example"], "https://community.example", "https://community.example"),
        (["https://community.example"], "https://fremd.example", None),
        (["*"], "https://fremd.example", "*"),
        ([], "https://community.example", None),
    ],
    ids=["erlaubt", "fremd", "stern", "leer"],
)
def test_cors(settings, origins, origin, allowed):
    settings.COMMUNITY_ORIGINS = origins
    response = zahlen(Origin=origin)
    assert response.get("Access-Control-Allow-Origin") == allowed


def test_cors_liste_mit_vary(settings):
    settings.COMMUNITY_ORIGINS = ["https://community.example"]
    assert "Origin" in zahlen(Origin="https://community.example")["Vary"]


def test_cache_spart_abfragen(settings, django_assert_num_queries):
    settings.COMMUNITY_CACHE_SECONDS = 10
    zahlen()
    with django_assert_num_queries(0):
        zahlen()


def test_cache_aus_mit_null(settings, campaign, valid_form, django_assert_num_queries):
    settings.COMMUNITY_CACHE_SECONDS = 0
    assert zahlen().json()["submissions"] == 0
    new_submission(valid_form)
    assert zahlen().json()["submissions"] == 1
    with django_assert_num_queries(3):
        zahlen()
    assert zahlen()["Cache-Control"] == "public, max-age=0"
