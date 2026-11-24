from datetime import timedelta

import pytest
from django.utils import timezone
from uploads_helper import Participant

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
def participant(campaign, valid_form, storage_dir):
    return Participant(valid_form)


@pytest.fixture
def another(campaign, valid_form, storage_dir):
    return lambda: Participant(valid_form)


def pytest_collection_modifyitems(config, items):
    """In CI (REQUIRE_GARAGE=1) dürfen Garage-Tests nicht still übersprungen werden."""
    import os

    from storage_backends import garage_available

    if os.environ.get("REQUIRE_GARAGE") and not garage_available():
        raise pytest.UsageError("REQUIRE_GARAGE ist gesetzt, aber Garage ist nicht konfiguriert")
