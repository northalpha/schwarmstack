import pytest


@pytest.mark.django_db
def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_startseite(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Schwarmstack" in response.content.decode()


def test_healthz_nur_get(client):
    assert client.post("/healthz").status_code == 405
