"""scripts/release.py: Release-Erkennung, Versionsprüfung, Release-Text (Ticket #99, ADR 0011)."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "release.py"


def _release():
    spec = importlib.util.spec_from_file_location("release", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


release = _release()


@pytest.mark.parametrize(
    ("version", "tags", "erwartet"),
    [
        ("0.2.0", [], True),
        ("0.1.0", [], False),  # Ausgangsstand ohne Tags ist kein Release
        ("0.2.0", ["v0.2.0"], False),  # schon getaggt
        ("0.2.1", ["v0.2.0"], True),
        ("0.10.0", ["v0.9.0", "v0.2.0"], True),  # numerisch, nicht als Text
        ("0.2.0", ["v0.3.0"], False),  # kleiner als der letzte Release
        ("1.0.0", ["v0.9.9", "anderes"], True),  # fremde Tags zählen nicht
    ],
)
def test_ist_release(version, tags, erwartet):
    assert release.ist_release(version, tags) is erwartet


def test_pruefen_lehnt_nicht_groessere_version_ab():
    with pytest.raises(release.ReleaseFehler, match="größer"):
        release.pruefe_version("0.2.0", ["v0.2.0"])


def test_pruefen_lehnt_ungueltige_version_ab():
    with pytest.raises(release.ReleaseFehler, match="X.Y.Z"):
        release.pruefe_version("v0.2", [])


def test_pruefen_nimmt_grosse_version():
    release.pruefe_version("0.2.0", ["v0.1.5"])


def test_tags_fuer_image():
    assert release.image_tags("0.2.3") == ["v0.2.3", "v0.2"]


def test_version_setzen(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "x"\nversion = "0.1.0"\nother = "version = 1"\n')
    release.setze_version(pyproject, "0.2.0")
    assert pyproject.read_text() == (
        '[project]\nname = "x"\nversion = "0.2.0"\nother = "version = 1"\n'
    )


CHANGELOG = """# Changelog

## Unveröffentlicht

Hinweis.

## 0.2.0

- Neu A.
- Neu B,
  zweizeilig.

## 0.1.0

- Alt.
"""


def test_release_text_ist_der_abschnitt():
    assert release.release_text(CHANGELOG, "0.2.0") == "- Neu A.\n- Neu B,\n  zweizeilig.\n"


def test_release_text_fehlt():
    with pytest.raises(release.ReleaseFehler, match="CHANGELOG"):
        release.release_text(CHANGELOG, "0.3.0")


def test_release_text_letzter_abschnitt():
    assert release.release_text(CHANGELOG, "0.1.0") == "- Alt.\n"
