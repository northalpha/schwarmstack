from datetime import timedelta

import pytest
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
def valid_form():
    return {
        "credit_name": "Ada Sternguck",
        "setup_description": "RedCat 51, ASI2600MM",
        "consent_project_use": "on",
        "consent_publish_credit": "on",
    }
