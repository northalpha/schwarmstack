#!/usr/bin/env python3
"""Erzeugt die Screenshots für die README: `uv run python scripts/screenshots.py`.

Startet die App mit lokalem Speicher in einem Wegwerf-Verzeichnis, legt eine Demo-Aktion (M 101)
an, lässt erfundene Teilnehmende über den Browser Dateien hochladen und fotografiert die Seiten.
Alle Daten stammen aus diesem Skript, nichts davon ist echt. Die Bilder landen in `docs/bilder/`.

Braucht Chromium für Playwright (`uv run playwright install chromium`, oder den Pfad in
`PLAYWRIGHT_CHROMIUM_EXECUTABLE`).
"""

import argparse
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))  # files.py erzeugt die Demo-Master

from files import fits  # noqa: E402
from PIL import Image  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

DESKTOP = {"width": 1280, "height": 800}
PHONE = {"width": 390, "height": 844}

# Erfundene Teilnehmende: (Name für die Nennung oder None, Setup, Master als (Kanal, Datei)).
PEOPLE = [
    ("Ada Sternguck", "RedCat 51, ASI2600MM Pro", [("L", 180), ("R", 180), ("G", 180)]),
    (None, "Skywatcher 200/800, Canon EOS 6D", [("RGB", 300)]),
    ("Max Nebelfleck", "Esprit 100ED, ASI533MC", [("Ha", 300), ("OIII", 300)]),
    ("Lena Galaxiensucher", "Celestron EdgeHD 8, ASI294MM", [("L", 120), ("B", 120)]),
]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def master(exposure: int, *, channel="L", seed="", width=1200, height=900, truncate=0) -> bytes:
    keywords = [
        ("EXPTIME", exposure, "Belichtung je Light in Sekunden"),
        ("STACKCNT", 24, "Anzahl Lights"),
        ("INSTRUME", "ASI2600MM", ""),
        ("TELESCOP", "RedCat 51", ""),
        # Verschieden je Datei, sonst zählt die App gleiche Bytes als Dublette.
        ("FILTER", channel, ""),
        ("OBJECT", f"M 101 {seed}".strip(), ""),
    ]
    planes = 3 if channel == "RGB" else None  # RGB braucht drei Ebenen, Mono-Kanäle eine
    return fits(width=width, height=height, planes=planes, keywords=keywords, truncate=truncate)


def run(*args, env, **kw):
    return subprocess.run(args, cwd=ROOT / "src", env=env, check=True, **kw)  # noqa: S603 (feste Befehle)


def start_app(data_dir: Path, port: int):
    env = {
        **os.environ,
        "DEBUG": "1",
        "DATA_DIR": str(data_dir),
        "STORAGE_BACKEND": "local",
        "DJANGO_SUPERUSER_PASSWORD": secrets.token_urlsafe(16),
        "PRIVACY_CONTACT": "datenschutz@example.org",
        "OPERATOR_NAME": "der Beispielverein",
        "OPERATOR_BEI": "beim Beispielverein",
        "OPERATOR_ADDRESS": "Beispielstraße 1, 12345 Beispielstadt",
        "HOSTER_NAME": "der Beispiel-Hoster",
        "HOSTER_BEI": "bei dem Beispiel-Hoster",
        "HOSTER_ADDRESS": "Hosterweg 2, 54321 Hosterstadt",
    }
    py = [sys.executable, "manage.py"]
    run(*py, "migrate", "-v", "0", env=env)
    now = datetime.now().astimezone()
    run(
        *py, "campaign", "--object", "M 101",
        "--starts-at", (now - timedelta(days=12)).isoformat(timespec="minutes"),
        "--ends-at", (now + timedelta(days=18)).isoformat(timespec="minutes"),
        "--quota-gib", "2", "--global-cap-gib", "1",
        env=env, stdout=subprocess.DEVNULL,
    )  # fmt: skip
    run(
        *py, "createsuperuser", "--noinput", "--username", "ada", "--email", "ada@example.org",
        env=env, stdout=subprocess.DEVNULL,
    )  # fmt: skip
    proc = subprocess.Popen(  # noqa: S603 (fester Befehl, kein Fremdwert)
        [*py, "runserver", f"127.0.0.1:{port}", "--noreload"],
        cwd=ROOT / "src", env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )  # fmt: skip
    url = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            if urllib.request.urlopen(f"{url}/healthz", timeout=1).read().strip() == b"ok":  # noqa: S310 (nur http://127.0.0.1)
                return proc, url, env["DJANGO_SUPERUSER_PASSWORD"]
        except OSError:
            time.sleep(0.5)
    proc.terminate()
    raise SystemExit("Die App ist nicht hochgekommen.")


def shoot(page, out: Path, name: str, *, full_page=True, target=None):
    page.wait_for_timeout(300)  # Schriften und Übergänge setzen lassen
    path = out / f"{name}.png"
    if target is not None:
        target.screenshot(path=path)
    else:
        page.screenshot(path=path, full_page=full_page)
    # Kleiner machen, ohne Bildinhalt zu ändern (verlustfrei).
    Image.open(path).save(path, optimize=True)
    print(f"  {path}  {path.stat().st_size // 1024} KiB")


def fill_form(page, name, setup):
    page.fill("[name=setup_description]", setup)
    if name:
        page.check("[name=consent_publish_credit]")
        page.fill("[name=credit_name]", name)
    page.check("[name=consent_project_use]")


def upload(page, tmp: Path, files):
    paths = []
    for index, (channel, data) in enumerate(files):
        path = tmp / f"m101_{channel}_{index}.fits"
        path.write_bytes(data)
        paths.append(path)
    page.wait_for_selector("#uploader", state="visible")
    page.set_input_files("#files", [str(p) for p in paths])
    for index, (channel, _) in enumerate(files):
        page.locator(".queue select").nth(index).select_option(channel)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "bilder")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_name:
        tmp = Path(tmp_name)
        proc, url, password = start_app(tmp / "daten", free_port())
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    executable_path=os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE") or None,
                    args=["--lang=de-DE"],
                    env={**os.environ, "LANGUAGE": "de"},  # deutsche Beschriftung der Dateiauswahl
                )

                def context(scheme="dark", viewport=DESKTOP):
                    return browser.new_context(
                        color_scheme=scheme, viewport=viewport, device_scale_factor=2,
                        locale="de-DE", timezone_id="Europe/Berlin",
                    )  # fmt: skip

                # 1. Teilnahmeseite, hell, dunkel und auf dem Handy
                print("Teilnahmeseite")
                for scheme in ("dark", "light"):
                    ctx = context(scheme)
                    page = ctx.new_page()
                    page.goto(url)
                    shoot(page, args.out, f"teilnahme-{'dunkel' if scheme == 'dark' else 'hell'}")
                    ctx.close()
                ctx = context("dark", PHONE)
                page = ctx.new_page()
                page.goto(url)
                shoot(page, args.out, "teilnahme-handy")
                ctx.close()

                # Demo-Teilnehmende laden hoch (ohne Bilder), damit die Statistik etwas zeigt.
                print("Demo-Teilnehmende")
                for name, setup, files in PEOPLE[1:]:
                    ctx = context()
                    page = ctx.new_page()
                    page.goto(url)
                    fill_form(page, name, setup)
                    page.click("button[type=submit]")
                    upload(
                        page, tmp, [(ch, master(exp, channel=ch, seed=name)) for ch, exp in files]
                    )
                    page.click(".uploader button.start")
                    page.wait_for_selector(
                        "table.masters td:has-text('angenommen')", timeout=120_000
                    )
                    ctx.close()

                # 2.-4. Eine Teilnahme mit Fortschritt, Prüfergebnis und „Angaben ändern“
                name, setup, files = PEOPLE[0]
                ctx = context()
                page = ctx.new_page()
                page.goto(url)
                fill_form(page, name, setup)
                page.click("button[type=submit]")
                reference = page.url.rstrip("/").rsplit("/", 1)[-1]
                batch = [
                    (ch, master(exp, channel=ch, seed=name, width=3000, height=2200))
                    for ch, exp in files[:2]
                ]
                # Eine unvollständige Datei zeigt, wie eine Ablehnung aussieht.
                batch.append(("B", master(180, channel="B", seed=name, truncate=40_000)))
                upload(page, tmp, batch)
                # Bandbreite drosseln, damit der Fortschritt sichtbar bleibt, danach freigeben.
                cdp = ctx.new_cdp_session(page)
                cdp.send("Network.enable")
                throttle = {"offline": False, "latency": 20, "downloadThroughput": -1}
                cdp.send(
                    "Network.emulateNetworkConditions",
                    {**throttle, "uploadThroughput": 1_500_000},
                )
                page.click(".uploader button.start")
                page.wait_for_timeout(4000)
                print("Upload")
                shoot(page, args.out, "upload-fortschritt", target=page.locator(".uploader"))
                cdp.send("Network.emulateNetworkConditions", {**throttle, "uploadThroughput": -1})
                page.wait_for_selector("table.masters td:has-text('abgelehnt')", timeout=120_000)
                page.wait_for_selector("table.masters td:has-text('angenommen')", timeout=120_000)
                page.wait_for_timeout(1500)
                print("Prüfergebnis")
                shoot(page, args.out, "pruefergebnis")
                print("Angaben ändern")
                page.goto(f"{url}/submission/{reference}/aendern/")
                shoot(page, args.out, "angaben-aendern")
                ctx.close()

                # 5. Betreiber-Statistik, dunkel und hell
                print("Betreiber-Statistik")
                for scheme in ("dark", "light"):
                    ctx = context(scheme, {"width": 1280, "height": 1350})
                    page = ctx.new_page()
                    page.goto(f"{url}/betrieb/login/")
                    page.fill("[name=username]", "ada")
                    page.fill("[name=password]", password)
                    page.click("input[type=submit]")
                    page.wait_for_load_state("networkidle")
                    shoot(
                        page,
                        args.out,
                        f"statistik-{'dunkel' if scheme == 'dark' else 'hell'}",
                        full_page=False,
                    )
                    ctx.close()
                browser.close()
        finally:
            proc.terminate()
            proc.wait(timeout=10)


if __name__ == "__main__":
    main()
