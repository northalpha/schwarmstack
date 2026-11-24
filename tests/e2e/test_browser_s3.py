"""E2E-Test im echten Browser: Uppy lädt direkt in S3 (Garage), Tickets #12 und #39.

Prüft nur den Weg Browser -> S3 -> Abschluss; fachliche Regeln testen die HTTP-Tests.
Läuft nur, wenn Garage gestartet ist (scripts/garage.sh start).
"""

import hashlib
import os
from datetime import timedelta

import pytest
from django.utils import timezone
from files import fits
from storage_backends import GARAGE_ENV, garage_available

from storage import get_storage
from submissions.models import Campaign, Master

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not garage_available(), reason="Garage nicht gestartet"),
]

playwright = pytest.importorskip("playwright.sync_api")


@pytest.fixture
def s3_settings(settings):
    settings.STORAGE_BACKEND = "s3"
    for name in GARAGE_ENV + ["S3_REGION", "S3_ADDRESSING_STYLE"]:
        setattr(settings, name, os.environ.get(name, ""))
    settings.S3_REGION = settings.S3_REGION or "garage"
    settings.S3_ADDRESSING_STYLE = settings.S3_ADDRESSING_STYLE or "path"
    return settings


@pytest.fixture
def browser():
    # Playwright betreibt eine eigene Ereignisschleife; die Datenbankzugriffe im Test sind sync.
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
    executable = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE") or None
    with playwright.sync_playwright() as p:
        instance = p.chromium.launch(executable_path=executable)
        yield instance
        instance.close()


@pytest.fixture
def campaign(transactional_db):
    """Wie in conftest.py, aber mit transactional_db: der Live-Server sieht die Daten."""
    now = timezone.now()
    return Campaign.objects.create(
        object_name="M 101",
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=1),
        quota=2 * 1024**3,
        global_cap=10 * 1024**3,
    )


def test_master_geht_direkt_in_s3(live_server, campaign, s3_settings, browser, tmp_path):
    data = fits(width=2000, height=1500)  # 12 MB, also zwei Teile à 8 MB
    path = tmp_path / "m101_L.fits"
    path.write_bytes(data)

    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(live_server.url)
    # Die Nennung hängt am Häkchen zur Veröffentlichung (Ticket #33).
    assert page.is_disabled("[name=credit_name]")
    page.check("[name=consent_publish_credit]")
    assert page.is_enabled("[name=credit_name]")
    page.fill("[name=credit_name]", "Ada Sternguck")
    page.check("[name=consent_project_use]")
    page.click("button[type=submit]")

    # upload.js wird mit defer geladen und blendet den Uploader erst ein, wenn es bereit ist.
    page.wait_for_selector("#uploader", state="visible")
    page.set_input_files("#files", str(path))
    page.locator(".queue select").first.select_option("L")
    page.click(".uploader button.start")
    page.wait_for_selector("table.masters td:has-text('angenommen')", timeout=60_000)
    assert errors == []

    master = Master.objects.get()
    assert master.state == Master.State.ACCEPTED
    assert master.sha256 == hashlib.sha256(data).hexdigest()  # vom Browser gemeldet
    storage = get_storage()
    assert storage.size(master.key) == len(data)
    assert storage.read_head(master.key, 80).startswith(b"SIMPLE  =")
    assert storage.size(master.sidecar_key) is not None

    # Die Master-Daten liefen nicht über den App-Server.
    assert "/_lokal/" not in page.content()


@pytest.mark.parametrize(
    ("blocked", "begun"),
    [
        # Die Teile kommen nie an; der Multipart-Upload im Speicher ist angelegt.
        ("partNumber=", lambda: Master.objects.exclude(upload_id="").exists()),
        # Schon die erste Sign-Anfrage kommt nie an: Master ohne upload_id.
        ("/signieren/", lambda: Master.objects.exists()),
    ],
    ids=["mit-upload-id", "ohne-upload-id"],
)
def test_nach_neuladen_unterbrochenen_upload_abbrechen(
    live_server, campaign, s3_settings, browser, tmp_path, blocked, begun
):
    path = tmp_path / "m101_L.fits"
    path.write_bytes(fits(width=2000, height=1500))

    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(live_server.url)
    page.check("[name=consent_project_use]")
    page.click("button[type=submit]")
    page.wait_for_selector("#uploader", state="visible")

    # Der Upload hängt, bis die Seite neu geladen wird.
    page.route(lambda url: blocked in url, lambda route: None)
    page.set_input_files("#files", str(path))
    page.locator(".queue select").first.select_option("L")
    page.click(".uploader button.start")
    for _ in range(300):
        if begun():
            break
        page.wait_for_timeout(100)
    else:
        pytest.fail("Upload hat nicht begonnen")
    page.unroute_all(behavior="ignoreErrors")
    page.reload()

    row = page.locator("table.masters tr[data-master-id]")
    row.locator("button.abort").click()
    row.locator("td:has-text('abgebrochen')").wait_for()
    assert Master.objects.get().state == Master.State.ABORTED

    page.reload()
    assert page.locator("table.masters").count() == 0  # Reservierung frei, Master weg
    assert errors == []
