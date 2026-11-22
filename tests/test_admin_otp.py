import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice

PASSWORD = "ein-langes-passwort-123"  # noqa: S105


@pytest.fixture
def admin_user(db):
    return get_user_model().objects.create_superuser("chef", "chef@example.org", PASSWORD)


@pytest.fixture
def device(admin_user):
    return TOTPDevice.objects.create(user=admin_user, name="test", confirmed=True)


def current_token(device: TOTPDevice) -> str:
    value = totp(device.bin_key, step=device.step, t0=device.t0, digits=device.digits)
    return str(value).zfill(device.digits)


def login_data(device, token, password=PASSWORD):
    return {
        "username": "chef",
        "password": password,
        "otp_device": device.persistent_id,
        "otp_token": token,
        "next": "/admin/",
    }


def test_ohne_anmeldung_zur_anmeldeseite(client):
    response = client.get("/admin/")
    assert response.status_code == 302
    assert "/admin/login/" in response["Location"]


def test_nur_passwort_reicht_nicht(client, admin_user, device):
    client.force_login(admin_user)  # Sitzung ohne bestätigten zweiten Faktor
    response = client.get("/admin/")
    assert response.status_code == 302
    assert "/admin/login/" in response["Location"]


def test_falscher_code_wird_abgelehnt(client, device):
    response = client.post("/admin/login/", login_data(device, "000000"))
    assert response.status_code == 200  # Formular mit Fehler
    assert client.get("/admin/").status_code == 302


def test_falsches_passwort_wird_abgelehnt(client, device):
    response = client.post("/admin/login/", login_data(device, current_token(device), "falsch"))
    assert response.status_code == 200
    assert client.get("/admin/").status_code == 302


def test_passwort_und_code_geben_zugang(client, device):
    response = client.post("/admin/login/", login_data(device, current_token(device)))
    assert response.status_code == 302
    page = client.get("/admin/")
    assert page.status_code == 200
    assert "Verwaltung" in page.content.decode()


def test_benutzer_ohne_geraet_kommt_nicht_hinein(client, admin_user):
    data = {"username": "chef", "password": PASSWORD, "otp_token": "123456", "next": "/admin/"}
    client.post("/admin/login/", data)
    assert client.get("/admin/").status_code == 302


def test_admin_pfad_ist_konfigurierbar():
    assert reverse("admin:index") == "/admin/"


def test_modelle_sind_im_admin(client, device):
    client.post("/admin/login/", login_data(device, current_token(device)))
    for name in ("event", "submission", "stack"):
        assert client.get(f"/admin/submissions/{name}/").status_code == 200
    assert client.get("/admin/uploads/uploadedfile/").status_code == 200
    assert client.get("/admin/packing/packjob/").status_code == 200
