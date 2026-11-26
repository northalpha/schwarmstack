import os
import tempfile

os.environ["DEBUG"] = "1"
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="schwarmstack-test-")
# Tests laufen standardmäßig gegen die lokale Platte; S3-Tests stellen gezielt um.
os.environ["STORAGE_BACKEND"] = "local"
os.environ["ADMIN_PATH"] = "betrieb-test"
# Die heutigen Werte der DZVF; der Datenschutzhinweis erscheint nur mit allen Angaben.
os.environ.setdefault("PRIVACY_CONTACT", "datenschutz@example.org")
os.environ.setdefault("OPERATOR_NAME", "der DZVF")
os.environ.setdefault("OPERATOR_BEI", "beim DZVF")
os.environ.setdefault("OPERATOR_ADDRESS", "Beispielstraße 1, 12345 Beispielstadt")
os.environ.setdefault("HOSTER_NAME", "die Hetzner Online GmbH")
os.environ.setdefault("HOSTER_BEI", "bei der Hetzner Online GmbH")
os.environ.setdefault("HOSTER_ADDRESS", "Industriestr. 25, 91710 Gunzenhausen")

from schwarmstack.settings import *  # noqa: E402,F403

# Ohne collectstatic gibt es kein Manifest; die Auslieferung im Image prüft
# test_statische_dateien.py mit der Einstellung aus schwarmstack.settings.
STORAGES = {
    **STORAGES,  # noqa: F405
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
# WhiteNoise warnt sonst bei jeder Anfrage, dass das Verzeichnis fehlt.
STATIC_ROOT.mkdir(parents=True, exist_ok=True)  # noqa: F405

# Testdatenbank als Datei wie im Betrieb (WAL, busy timeout), nicht pytest-djangos In-Memory-
# Datenbank mit geteiltem Cache: Dort sperrt SQLite je Tabelle und meldet „database table is
# locked“ sofort, ohne zu warten, sobald Live-Server-Thread und Test-Thread gleichzeitig
# zugreifen (E2E-Tests).
DATABASES["default"]["TEST"] = {"NAME": DATA_DIR / "test-db.sqlite3"}  # noqa: F405
