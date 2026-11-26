"""Sicherheits-Header auf allen Antworten, auch auf Admin- und Fehlerseiten (Ticket #122)."""

import pytest
from admin_helper import ADMIN

from schwarmstack.security_headers import content_security_policy

pytestmark = pytest.mark.django_db


def direktiven(policy: str) -> dict[str, list[str]]:
    teile = (t.strip().split() for t in policy.split(";") if t.strip())
    return {t[0]: t[1:] for t in teile}


def pruefe_header(response):
    assert response["X-Frame-Options"] == "DENY"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Referrer-Policy"] == "same-origin"
    assert "camera=()" in response["Permissions-Policy"]
    assert "Content-Security-Policy-Report-Only" not in response
    d = direktiven(response["Content-Security-Policy"])
    assert d["default-src"] == ["'self'"]
    assert d["script-src"] == ["'self'"]
    assert d["frame-ancestors"] == ["'none'"]
    assert d["base-uri"] == ["'self'"]
    assert d["form-action"] == ["'self'"]
    assert "'unsafe-inline'" not in response["Content-Security-Policy"]
    assert "'unsafe-eval'" not in response["Content-Security-Policy"]


def test_startseite(client, campaign):
    pruefe_header(client.get("/"))


def test_submission_seite(client, reference):
    pruefe_header(client.get(f"/submission/{reference}/"))


def test_healthz(client, settings, tmp_path):
    settings.STORAGE_LOCAL_DIR = tmp_path
    pruefe_header(client.get("/healthz"))


def test_anmeldeseite_des_admin(client):
    response = client.get(ADMIN, follow=True)
    assert response.status_code == 200
    pruefe_header(response)


def test_statistik_im_admin(operator_client):
    response = operator_client.get(ADMIN)
    assert response.status_code == 200
    pruefe_header(response)


def test_seite_nicht_gefunden(client):
    response = client.get("/gibt-es-nicht/")
    assert response.status_code == 404
    pruefe_header(response)


def test_ungueltiger_host(client):
    response = client.get("/", headers={"host": "fremd.example"})
    assert response.status_code == 400
    pruefe_header(response)


def test_serverfehler(client, campaign, monkeypatch):
    def kaputt(*args, **kwargs):
        raise RuntimeError("kaputt")

    monkeypatch.setattr("submissions.views.render", kaputt)
    client.raise_request_exception = False
    response = client.get("/")
    assert response.status_code == 500
    pruefe_header(response)


def test_nur_ansehen_report_only(client, settings, campaign):
    settings.CSP_REPORT_ONLY = True
    response = client.get("/")
    assert "Content-Security-Policy" not in response
    assert direktiven(response["Content-Security-Policy-Report-Only"])["script-src"] == ["'self'"]


@pytest.mark.parametrize(
    ("endpunkt", "stil", "bucket", "erwartet"),
    [
        ("https://s3.example.org", "virtual", "master", "https://master.s3.example.org"),
        ("https://s3.example.org", "path", "master", "https://s3.example.org"),
        ("http://127.0.0.1:3900", "path", "master", "http://127.0.0.1:3900"),
        ("", "virtual", "master", "https://*.amazonaws.com"),
    ],
)
def test_connect_src_enthaelt_den_s3_host(settings, endpunkt, stil, bucket, erwartet):
    settings.STORAGE_BACKEND = "s3"
    settings.S3_ENDPOINT_URL = endpunkt
    settings.S3_ADDRESSING_STYLE = stil
    settings.S3_BUCKET = bucket
    assert direktiven(content_security_policy())["connect-src"] == ["'self'", erwartet]


def test_connect_src_ohne_s3_nur_eigener_ursprung(settings):
    settings.STORAGE_BACKEND = "local"
    assert direktiven(content_security_policy())["connect-src"] == ["'self'"]


def test_statistik_hat_kein_inline_style(operator_client):
    html = operator_client.get(ADMIN).content.decode()
    assert "<style" not in html
