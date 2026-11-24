from datetime import timedelta

import pytest
from admin_helper import PASSWORD
from django.test import Client
from django.utils import timezone

from submissions.models import Campaign

GIB = 1024**3


@pytest.fixture
def campaign(db):
    now = timezone.now()
    return Campaign.objects.create(
        object_name="M 101",
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=30),
        quota=2 * GIB,
        global_cap=400 * GIB,
    )


@pytest.fixture
def storage_dir(settings, tmp_path):
    """Lokaler Speicher-Adapter in einem eigenen Verzeichnis je Test."""
    settings.STORAGE_LOCAL_DIR = tmp_path / "speicher"
    return settings.STORAGE_LOCAL_DIR


@pytest.fixture
def valid_form():
    return {
        "credit_name": "Ada Sternguck",
        "setup_description": "RedCat 51, ASI2600MM",
        "consent_project_use": "on",
        "consent_publish_credit": "on",
    }


@pytest.fixture
def operator(db, django_user_model):
    """Ein Betreiber-Konto für den Admin."""
    return django_user_model.objects.create_superuser("ada", "ada@example.org", PASSWORD)


@pytest.fixture
def operator_client(operator):
    """Test-Client, als Betreiber angemeldet."""
    client = Client()
    client.force_login(operator)
    return client


@pytest.fixture(scope="session")
def moto_endpoint():
    """S3 mit moto als eigener Server, einmal je Testlauf."""
    from moto.server import ThreadedMotoServer

    server = ThreadedMotoServer(ip_address="127.0.0.1", port=0, verbose=False)
    server.start()
    host, port = server.get_host_and_port()
    yield f"http://{host}:{port}"
    server.stop()


def pytest_collection_modifyitems(config, items):
    """In CI (REQUIRE_GARAGE=1) dürfen Garage-Tests nicht still übersprungen werden."""
    import os

    from storage_backends import garage_available

    if os.environ.get("REQUIRE_GARAGE") and not garage_available():
        raise pytest.UsageError("REQUIRE_GARAGE ist gesetzt, aber Garage ist nicht konfiguriert")
