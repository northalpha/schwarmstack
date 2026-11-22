from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice


@pytest.fixture
def staff(db):
    return get_user_model().objects.create_superuser("chef", "c@example.org", "pw-123456789")


def run(*args):
    out = StringIO()
    call_command("otp_setup", *args, stdout=out)
    return out.getvalue()


def test_legt_geraet_und_codes_an(staff):
    output = run("chef")
    assert "otpauth://totp/" in output
    device = TOTPDevice.objects.get(user=staff)
    assert device.confirmed
    assert StaticDevice.objects.get(user=staff).token_set.count() == 8


def test_zweiter_aufruf_ohne_reset_scheitert(staff):
    run("chef")
    with pytest.raises(CommandError):
        run("chef")


def test_reset_ersetzt_das_geraet(staff):
    run("chef")
    old = TOTPDevice.objects.get(user=staff).key
    run("chef", "--reset")
    assert TOTPDevice.objects.get(user=staff).key != old


def test_unbekannter_benutzer(db):
    with pytest.raises(CommandError):
        run("niemand")


def test_kein_admin(db):
    get_user_model().objects.create_user("gast", "g@example.org", "pw-123456789")
    with pytest.raises(CommandError):
        run("gast")
