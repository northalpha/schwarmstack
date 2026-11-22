import datetime

import pytest
from django.utils import timezone
from factories import GIB, make_event, make_file, make_stack, make_submission

from packing.models import PackJob
from packing.services import enqueue_pack
from submissions.models import Stack
from submissions.quota import refusal_reason, used_bytes_event, used_bytes_submission
from uploads.models import UploadedFile

MIB = 1024**2


@pytest.fixture
def stack(db):
    event = make_event(
        quota_bytes_per_submission=GIB, global_cap_bytes=3 * GIB, max_file_bytes=GIB // 2
    )
    return make_stack(make_submission(event))


@pytest.mark.django_db
class TestZaehlung:
    def test_nur_zaehlende_zustaende(self, stack):
        for state in UploadedFile.COUNTED_STATES:
            make_file(stack, 10 * MIB, state=state)
        for state in (UploadedFile.REJECTED, UploadedFile.ABORTED, UploadedFile.DELETED):
            make_file(stack, 999 * MIB, state=state)
        assert used_bytes_submission(stack.submission) == 40 * MIB
        assert used_bytes_event(stack.submission.event) == 40 * MIB

    def test_abgelehnte_datei_gibt_quote_frei(self, stack):
        file = make_file(stack, 500 * MIB, state=UploadedFile.VALIDATING)
        make_file(stack, 500 * MIB, name="b.fits")
        assert refusal_reason(stack, 100 * MIB) == "Deine Quote ist ausgeschöpft."
        file.state = UploadedFile.REJECTED
        file.save()
        assert refusal_reason(stack, 100 * MIB) is None

    def test_leer(self, stack):
        assert used_bytes_submission(stack.submission) == 0


@pytest.mark.django_db
class TestRefusal:
    def test_ok(self, stack):
        assert refusal_reason(stack, 100 * MIB) is None

    def test_unbekannte_groesse(self, stack):
        assert refusal_reason(stack, 0) == "Die Dateigröße ist unbekannt."

    def test_datei_zu_gross(self, stack):
        assert refusal_reason(stack, GIB // 2 + 1) == "Die Datei ist zu groß."

    def test_quote_genau_am_limit_ist_erlaubt(self, stack):
        make_file(stack, GIB // 2)
        assert refusal_reason(stack, GIB // 2) is None
        assert refusal_reason(stack, GIB // 2 + 1) is not None

    def test_gesamtgrenze(self, stack):
        event = stack.submission.event
        for i in range(2):
            other = make_stack(make_submission(event))
            make_file(other, GIB, name=f"{i}.fits")
        other = make_stack(make_submission(event))
        make_file(other, GIB - 100 * MIB)
        assert refusal_reason(stack, 200 * MIB) == "Die Gesamtkapazität des Events ist erreicht."
        assert refusal_reason(stack, 50 * MIB) is None

    def test_gesperrte_abgabe(self, stack):
        stack.submission.is_blocked = True
        stack.submission.save()
        assert refusal_reason(stack, MIB) == "Diese Abgabe ist gesperrt."

    def test_geschlossenes_event(self, stack):
        event = stack.submission.event
        event.closes_at = timezone.now() - datetime.timedelta(minutes=1)
        event.save()
        assert refusal_reason(stack, MIB) == "Das Event ist geschlossen."

    def test_abgeschlossener_stack(self, stack):
        stack.state = Stack.CLOSED
        stack.save()
        assert refusal_reason(stack, MIB) == "Dieser Stack ist abgeschlossen."


@pytest.mark.django_db
class TestEnqueue:
    def test_ein_auftrag_je_stack(self, stack):
        job1 = enqueue_pack(stack)
        job2 = enqueue_pack(stack)
        assert job1.pk == job2.pk
        assert PackJob.objects.filter(stack=stack, kind=PackJob.PACK).count() == 1
        stack.refresh_from_db()
        assert stack.state == Stack.QUEUED and stack.closed_at

    def test_neu_packen_setzt_auftrag_zurueck(self, stack):
        job = enqueue_pack(stack)
        job.state, job.attempts, job.locked_by = PackJob.FAILED, 3, "w1"
        job.save()
        enqueue_pack(stack)
        job.refresh_from_db()
        assert (job.state, job.attempts, job.locked_by) == (PackJob.QUEUED, 0, "")
