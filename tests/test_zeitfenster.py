"""Die zentrale Regel für das Zeitfenster der Aktion (Ticket #10)."""

from datetime import UTC, datetime, timedelta

import pytest

from submissions.models import Campaign, Phase

START = datetime(2027, 3, 1, tzinfo=UTC)
END = datetime(2027, 4, 1, tzinfo=UTC)
SECOND = timedelta(seconds=1)


@pytest.fixture
def aktion():
    return Campaign(object_name="M 101", starts_at=START, ends_at=END, quota=1, global_cap=1)


@pytest.mark.parametrize(
    ("now", "phase"),
    [
        (START - SECOND, Phase.BEFORE),
        (START, Phase.OPEN),
        (END - SECOND, Phase.OPEN),
        (END, Phase.GRACE),
        (END + timedelta(hours=6) - SECOND, Phase.GRACE),
        (END + timedelta(hours=6), Phase.CLOSED),
    ],
)
def test_phasen_und_grenzen(aktion, now, phase):
    assert aktion.phase(now) is phase


def test_nachfrist_kommt_aus_der_aktion(aktion):
    aktion.grace_period = timedelta(hours=1)
    assert aktion.phase(END + timedelta(hours=1)) is Phase.CLOSED


def test_neue_submissions_nur_waehrend_der_aktion(aktion):
    assert not aktion.phase(START - SECOND).accepts_new_submissions
    assert aktion.phase(START).accepts_new_submissions
    assert not aktion.phase(END).accepts_new_submissions
    assert not aktion.phase(END + timedelta(days=1)).accepts_new_submissions
