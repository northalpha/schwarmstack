"""Regressionstests aus dem Review gegen die OWASP Top 10 (Ticket #123).

Jeder Test hält eine Sicherheitsannahme fest, die beim Review von Hand bestätigt wurde. Die
Annahmen, die andere Testdateien schon prüfen, stehen nicht doppelt hier.
"""

import json
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from django.contrib.auth.password_validation import validate_password
from django.core import signing
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import get_resolver
from files import _header, xisf
from uploads_helper import start

from submissions import access, validation

pytestmark = pytest.mark.django_db


# -- Anmeldung: Passwort-Regeln -----------------------------------------------------------------


@pytest.mark.parametrize("password", ["kurz", "12345678901234", "password1234"])
def test_schwache_passwoerter_der_betreiber_werden_abgelehnt(password):
    with pytest.raises(ValidationError):
        validate_password(password)


def test_ein_gutes_passwort_wird_angenommen():
    validate_password("sternenstaub-2026-kometenschweif")


# -- Zugriffskontrolle: Cookie-Zugang (ADR 0002) --------------------------------------------------


REFERENCE_ROUTES = [
    ("get", "submission", {}),
    ("get", "change_details", {}),
    ("get", "change_photo", {}),
    ("get", "delete_photo", {}),
    ("get", "photo", {}),
    ("get", "photo_thumbnail", {}),
    ("get", "delete_submission", {}),
    ("get", "revoke_credit", {}),
    ("get", "grant_credit", {}),
    ("post", "upload_start", {}),
    ("get", "delete_master", {"master_id": uuid.uuid4()}),
    ("post", "upload_sign", {"master_id": uuid.uuid4()}),
    ("post", "upload_abort", {"master_id": uuid.uuid4()}),
    ("post", "upload_finish", {"master_id": uuid.uuid4()}),
    ("post", "exposure", {"master_id": uuid.uuid4()}),
]


def test_jede_route_mit_submission_id_steht_in_der_zugriffsliste():
    """Kommt eine Route mit `reference` dazu, muss sie hier mit aufgenommen werden."""
    names = set()
    for pattern in get_resolver().url_patterns:
        for sub in getattr(pattern, "url_patterns", []):
            if "reference" in str(sub.pattern):
                names.add(sub.name)
    assert names - {"legacy_submission"} == {name for _, name, _ in REFERENCE_ROUTES}


@pytest.mark.parametrize(("method", "name", "extra"), REFERENCE_ROUTES)
def test_cookie_von_a_oeffnet_submission_b_nicht(participant, another, method, name, extra):
    from django.urls import reverse

    b = another()
    url = reverse(name, kwargs={"reference": b.reference, **extra})
    response = getattr(participant.client, method)(url)
    assert response.status_code == 404
    assert getattr(Client(), method)(url).status_code == 404  # ohne Cookie ebenso


@pytest.mark.parametrize(
    "forge",
    [
        lambda ref: ref,  # unsigniert
        lambda ref: signing.dumps(ref, salt="submissions.access"),  # anderes Format
        lambda ref: signing.get_cookie_signer(salt="anderes.salz").sign(ref),  # falsches Salz
        lambda ref: signing.get_cookie_signer(salt="submissions.access").sign(ref)[:-2] + "xx",
    ],
    ids=["unsigniert", "anderes-format", "falsches-salz", "kaputte-signatur"],
)
def test_gefaelschtes_cookie_gibt_keinen_zugang(participant, another, forge):
    b = another()
    client = Client()
    client.cookies[access.COOKIE_NAME] = forge(b.reference)
    assert client.get(f"/submission/{b.reference}/").status_code == 404


def test_cookie_ist_httponly_samesite_und_im_betrieb_secure(client, campaign, valid_form, settings):
    settings.SUBMISSION_COOKIE_SECURE = True
    client.post("/", valid_form)
    cookie = client.cookies[access.COOKIE_NAME]
    assert cookie["httponly"]
    assert cookie["samesite"] == "Lax"
    assert cookie["secure"]


def test_cookie_der_teilnehmenden_oeffnet_den_admin_nicht(participant):
    from admin_helper import ADMIN

    response = participant.client.get(ADMIN)
    assert response.status_code == 302
    assert response["Location"].startswith(f"{ADMIN}login/")


def test_admin_unterseiten_verlangen_anmeldung(client, campaign, participant):
    from admin_helper import ADMIN

    for suffix in [
        "submissions/submission/",
        "submissions/campaign/",
        "auth/user/",
        "auth/user/1/",
    ]:
        response = client.get(ADMIN + suffix)
        assert response.status_code == 302, suffix
        assert "/login/" in response["Location"], suffix


# -- Upload und Signatur --------------------------------------------------------------------------


def _signed(client, reference, body, **request):
    from uploads_helper import sign

    return sign(client, reference, body["masterId"], **request)


def test_signatur_gilt_nur_fuer_den_eigenen_schluessel(participant):
    own = start(participant.client, participant.reference, size=10).json()
    other = start(participant.client, participant.reference, size=10).json()
    response = _signed(
        participant.client, participant.reference, own,
        method="GET", key=other["key"], uploadId="u",
    )  # fmt: skip
    assert response.status_code == 400


def test_signatur_gilt_nicht_fuer_den_schluessel_einer_fremden_submission(participant, another):
    b = another()
    foreign = start(b.client, b.reference, size=10).json()
    own = start(participant.client, participant.reference, size=10).json()
    response = _signed(
        participant.client, participant.reference, own,
        method="GET", key=foreign["key"], uploadId="u",
    )  # fmt: skip
    assert response.status_code == 400


def test_upload_id_laesst_sich_nach_dem_ersten_signieren_nicht_wechseln(participant):
    body = start(participant.client, participant.reference, size=10).json()
    ok = _signed(
        participant.client, participant.reference, body,
        method="GET", key=body["key"], uploadId="erste",
    )  # fmt: skip
    assert ok.status_code == 200
    swapped = _signed(
        participant.client, participant.reference, body,
        method="GET", key=body["key"], uploadId="zweite",
    )  # fmt: skip
    assert swapped.status_code == 400


@pytest.mark.parametrize("method", ["HEAD", "PATCH", "DELETE-ALL", None, 5])
def test_nur_bekannte_methoden_werden_signiert(participant, method):
    body = start(participant.client, participant.reference, size=10).json()
    response = _signed(
        participant.client, participant.reference, body,
        method=method, key=body["key"], uploadId="u",
    )  # fmt: skip
    assert response.status_code == 400


@pytest.mark.parametrize(
    "filename", ["../../etc/passwd.fits", "a/b.fits", "m101.fits/../../x.xisf", "x.fits\x00.exe"]
)
def test_dateiname_mit_pfad_landet_nicht_im_schluessel(participant, filename):
    from submissions.models import Master

    response = start(participant.client, participant.reference, filename=filename, size=10)
    if response.status_code == 201:
        key = Master.objects.get(public_id=response.json()["masterId"]).key
        assert ".." not in key
        assert key.startswith(f"{participant.reference}/")
        assert "/" not in key.removeprefix(f"{participant.reference}/")
    else:
        assert response.status_code == 400


def test_lokaler_endpunkt_nimmt_nur_den_eigenen_salz(participant):
    """Ein mit anderem Salz signierter Link (z. B. aus einer Sitzung) ist kein Upload-Link."""
    token = signing.dumps({"m": "GET", "k": "x/y.fits", "e": 9_999_999_999}, salt="anderes.salz")
    assert Client().get(f"/_lokal/s3/{token}/").status_code == 403


def test_lokaler_endpunkt_legt_keine_schluessel_mit_pfadtricks_an(participant, storage_dir):
    from storage.local import S3Request, sign_token

    token = sign_token(S3Request("POST", "../ausserhalb.fits"))
    response = Client().post(f"/_lokal/s3/{token}/")
    assert response.status_code == 400
    assert not (Path(storage_dir).parent / "ausserhalb.fits").exists()


def test_fehlermeldung_des_lokalen_endpunkts_nennt_den_link_nicht(participant):
    token = "geheimer-link-inhalt"
    response = Client().get(f"/_lokal/s3/{token}/")
    assert response.status_code == 403
    assert token not in response.content.decode()


# -- Konfiguration aus der Umgebung ---------------------------------------------------------------

_ROOT = Path(__file__).resolve().parent.parent


def _settings_with(env: dict[str, str]):
    """Importiert die Settings in einem frischen Prozess mit genau dieser Umgebung."""
    import os

    base = {"PATH": os.environ["PATH"], "DATA_DIR": os.environ["DATA_DIR"]}
    return subprocess.run(  # noqa: S603
        [
            sys.executable, "-c",
            "import json, schwarmstack.settings as s;"
            "print(json.dumps({'debug': s.DEBUG, 'hosts': s.ALLOWED_HOSTS,"
            " 'secure': s.SUBMISSION_COOKIE_SECURE, 'xff': s.TRUST_X_FORWARDED_FOR}))",
        ],
        env={**base, **env},
        cwd=_ROOT / "src",
        capture_output=True,
        text=True,
        check=False,
    )  # fmt: skip


def test_ohne_geheimen_schluessel_startet_die_app_nicht_im_betrieb():
    result = _settings_with({"ADMIN_PATH": "x", "ALLOWED_HOSTS": "a.example"})
    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY" in result.stderr


def test_ohne_admin_pfad_startet_die_app_nicht_im_betrieb():
    result = _settings_with({"DJANGO_SECRET_KEY": "k", "ALLOWED_HOSTS": "a.example"})
    assert result.returncode != 0
    assert "ADMIN_PATH" in result.stderr


def test_ohne_debug_gelten_die_sicheren_voreinstellungen():
    result = _settings_with(
        {"DJANGO_SECRET_KEY": "k", "ADMIN_PATH": "x", "ALLOWED_HOSTS": "a.example"}
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "debug": False, "hosts": ["a.example"], "secure": True, "xff": True,
    }  # fmt: skip


def test_ohne_debug_und_ohne_hosts_erlaubt_django_keinen_host():
    result = _settings_with({"DJANGO_SECRET_KEY": "k", "ADMIN_PATH": "x"})
    assert json.loads(result.stdout)["hosts"] == []


def test_unbekannter_host_wird_abgewiesen(settings):
    settings.ALLOWED_HOSTS = ["schwarmstack.example"]
    assert Client().get("/healthz", HTTP_HOST="boese.example").status_code == 400


def test_s3_endpunkt_kommt_nur_aus_der_umgebung_nie_aus_einer_anfrage(participant, settings):
    """Kein Wert aus Anfragen der Teilnehmenden fließt in die S3-Adresse (SSRF)."""
    from storage import S3Request
    from storage.s3 import S3Storage

    storage = S3Storage(bucket="b", endpoint_url="https://s3.example", access_key_id="k",
                        secret_access_key="s", region="r", addressing_style="path")  # fmt: skip
    url = storage.presign(S3Request("POST", "SW-ABCD/x.fits"))
    assert url.startswith("https://s3.example/b/SW-ABCD/x.fits")


# -- Logging und Meldungen ------------------------------------------------------------------------


def test_zugangsdaten_landen_nicht_im_log_der_betriebsmeldung(settings, caplog, mailoutbox):
    import smtplib
    from unittest import mock

    from schwarmstack import notices

    settings.OPERATOR_EMAILS = ["betrieb@example.org"]
    settings.EMAIL_HOST_PASSWORD = "geheimes-smtp-passwort"  # noqa: S105
    with (
        mock.patch("schwarmstack.notices.send_mail", side_effect=smtplib.SMTPException("kaputt")),
        caplog.at_level("DEBUG"),
    ):
        assert notices.send("Betreff", "Text") is False
    assert "geheimes-smtp-passwort" not in caplog.text


def test_weder_cookie_noch_passwort_stehen_im_log(participant, operator, caplog):
    from admin_helper import ADMIN

    with caplog.at_level("DEBUG"):
        participant.client.get(f"/submission/{participant.reference}/")
        Client().get("/submission/SW-ZZZZ/")
        Client().post(
            f"{ADMIN}login/",
            {"username": "ada", "password": "falsches-passwort-xyz", "next": ADMIN},
        )
    cookie = participant.client.cookies[access.COOKIE_NAME].value
    assert cookie not in caplog.text
    assert "falsches-passwort-xyz" not in caplog.text


# -- Dateien verarbeiten: Header von XISF und FITS ------------------------------------------------


def _check(data, suffix, channel="L"):
    return validation.check(
        data, suffix=suffix, channel=channel, channel_label=channel, size=len(data)
    )


@pytest.mark.parametrize(
    "xml",
    [
        '<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><xisf>&e;</xisf>',
        '<!DOCTYPE x [<!ENTITY e SYSTEM "http://127.0.0.1:1/x">]><xisf>&e;</xisf>',
        '<!DOCTYPE x [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">'
        "]><xisf>&b;</xisf>",
        '<!DOCTYPE x SYSTEM "http://127.0.0.1:1/x.dtd"><xisf/>',
    ],
    ids=["externe-datei", "externe-url", "entity-expansion", "externe-dtd"],
)
def test_xisf_mit_entitaeten_oder_dtd_wird_abgelehnt_ohne_sie_aufzuloesen(xml):
    result = _check(xisf(xml=xml), ".xisf")
    assert not result.ok
    assert result.category is validation.Category.DAMAGED
    assert "passwd" not in result.reason


def test_xisf_mit_riesiger_geometrie_braucht_entsprechend_viel_datei():
    """Eine Datei, die riesige Maße nur behauptet, ist kürzer als ihr Header angibt."""
    data = xisf(width=2000, height=2000, truncate=100)
    result = _check(data, ".xisf")
    assert not result.ok
    assert result.category is validation.Category.DAMAGED


def test_fits_mit_riesigen_achsen_wird_ohne_speicherbedarf_abgelehnt():
    head = _header(
        [
            f"SIMPLE  = {'T':>20}",
            f"BITPIX  = {-32:>20}",
            f"NAXIS   = {2:>20}",
            f"NAXIS1  = {10**9:>20}",
            f"NAXIS2  = {10**9:>20}",
            "END",
        ]
    )
    result = validation.check(head, suffix=".fits", channel="L", channel_label="L", size=len(head))
    assert not result.ok
    assert result.category is validation.Category.DAMAGED
