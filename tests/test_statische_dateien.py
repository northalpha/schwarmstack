"""Statische Dateien kommen im Container ohne eigenen Webserver aus der App (Ticket #27)."""

from django.core.management import call_command
from django.templatetags.static import static
from django.test import Client

from schwarmstack import settings as einstellungen_im_image


def test_uppy_wird_ohne_debug_ausgeliefert(settings, tmp_path):
    settings.DEBUG = False
    settings.STATIC_ROOT = tmp_path
    settings.STORAGES = einstellungen_im_image.STORAGES
    call_command("collectstatic", "--noinput", verbosity=0)

    url = static("submissions/vendor/uppy/uppy.min.js")
    response = Client().get(url)

    assert response.status_code == 200
    assert b"Uppy" in b"".join(response.streaming_content)
