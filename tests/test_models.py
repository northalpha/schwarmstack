import datetime

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from factories import make_event, make_stack, make_submission

from submissions.models import Consent, ExposureLine, SocialLink, detect_platform


@pytest.mark.django_db
class TestEvent:
    def test_standardwerte_kommen_aus_den_settings(self, settings):
        settings.DEFAULT_QUOTA_BYTES = 1024**3
        settings.DEFAULT_GLOBAL_CAP_BYTES = 4 * 1024**3
        event = make_event()
        assert event.quota_bytes_per_submission == 1024**3
        assert event.global_cap_bytes == 4 * 1024**3
        assert event.max_file_bytes == 2 * 1024**3
        assert event.altcha_enabled is False
        assert event.use_fpack is False

    def test_origins_nur_https_ohne_pfad(self):
        event = make_event(entry_origins=["https://projekt.example.org"])
        event.full_clean()
        for bad in ["http://projekt.example.org", "https://x.org/pfad", "projekt.org", "https://"]:
            event.entry_origins = [bad]
            with pytest.raises(ValidationError):
                event.clean()

    def test_origins_muss_liste_sein(self):
        event = make_event(entry_origins="https://projekt.example.org")
        with pytest.raises(ValidationError):
            event.clean()

    def test_ende_nach_beginn(self):
        now = timezone.now()
        event = make_event(opens_at=now, closes_at=now - datetime.timedelta(days=1))
        with pytest.raises(ValidationError):
            event.clean()

    def test_is_open(self):
        now = timezone.now()
        day = datetime.timedelta(days=1)
        assert make_event(slug="a").is_open()
        assert not make_event(slug="b", active=False).is_open()
        assert not make_event(slug="c", opens_at=now + day).is_open()
        assert not make_event(slug="d", closes_at=now - day).is_open()
        assert make_event(slug="e", opens_at=now - day, closes_at=now + day).is_open()


@pytest.mark.django_db
class TestSubmission:
    def test_bortle_1_bis_9(self):
        sub = make_submission(bortle=5)
        sub.full_clean(exclude=["token_hash"])
        sub.bortle = 10
        with pytest.raises(ValidationError):
            sub.full_clean(exclude=["token_hash"])

    def test_name_mindestens_zwei_zeichen(self):
        sub = make_submission(display_name="A")
        with pytest.raises(ValidationError):
            sub.clean()

    def test_token_hash_ist_eindeutig(self):
        first = make_submission()
        with pytest.raises(Exception):  # noqa: B017, PT011 - IntegrityError der DB
            make_submission(first.event, token_hash=first.token_hash)


@pytest.mark.django_db
class TestLinks:
    def test_plattform_wird_erkannt(self):
        assert detect_platform("https://www.astrobin.com/users/x/") == "AstroBin"
        assert detect_platform("https://instagram.com/x") == "Instagram"
        assert detect_platform("https://youtu.be/abc") == "YouTube"
        assert detect_platform("https://beispiel.de/") == "Webseite"
        assert detect_platform("https://nicht-instagram.com/") == "Webseite"

    def test_nur_https(self):
        link = SocialLink(submission=make_submission(), url="http://example.org")
        with pytest.raises(ValidationError):
            link.clean()

    def test_hoechstens_vier(self):
        sub = make_submission()
        for i in range(4):
            SocialLink.objects.create(submission=sub, url=f"https://example.org/{i}")
        fifth = SocialLink(submission=sub, url="https://example.org/5")
        with pytest.raises(ValidationError):
            fifth.clean()

    def test_plattform_wird_gespeichert(self):
        link = SocialLink.objects.create(submission=make_submission(), url="https://flickr.com/x")
        assert link.platform == "Flickr"


@pytest.mark.django_db
class TestConsent:
    def test_erteilen_und_widerrufen(self):
        consent = Consent.objects.create(submission=make_submission(), kind=Consent.STATUS_MAILS)
        consent.grant("v1")
        assert consent.granted and consent.granted_at and consent.text_version == "v1"
        consent.revoke()
        assert not consent.granted and consent.revoked_at

    def test_je_art_nur_einmal(self):
        sub = make_submission()
        Consent.objects.create(submission=sub, kind=Consent.PRIVACY_READ)
        with pytest.raises(Exception):  # noqa: B017, PT011
            Consent.objects.create(submission=sub, kind=Consent.PRIVACY_READ)


@pytest.mark.django_db
class TestStack:
    def test_blende_wird_berechnet(self):
        stack = make_stack(focal_length_mm=800, aperture_mm=200)
        assert float(stack.focal_ratio) == 4.0

    def test_blende_von_hand_bleibt(self):
        stack = make_stack(focal_length_mm=800, aperture_mm=200, focal_ratio=5.6)
        assert float(stack.focal_ratio) == 5.6

    def test_gesamtbelichtung(self):
        stack = make_stack()
        ExposureLine.objects.create(stack=stack, filter="Ha", count=42, seconds=300)
        ExposureLine.objects.create(stack=stack, filter="L", count=10, seconds=60)
        assert stack.total_exposure_seconds == 42 * 300 + 600

    def test_anfangszustand_offen(self):
        assert make_stack().state == "open"
