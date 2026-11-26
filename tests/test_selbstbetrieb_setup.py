"""Fehlerwege von deploy/selbst/setup.sh (Ticket #100, ADR 0011).

Der Lauf mit Docker, Garage und Caddy gehört zum Installer-Test der CI (#105). Hier stehen nur
die Wege, die vor dem ersten Docker-Aufruf enden und nichts anfassen.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

SELBST = Path(__file__).resolve().parent.parent / "deploy" / "selbst"
SETUP = SELBST / "setup.sh"
KEINE_ANGABEN = {
    "PATH": "/usr/bin:/bin",
    "HOME": "/nonexistent",
}


def setup(*args, env=None):
    return subprocess.run(  # noqa: S603  # festes Skript im Repo
        [str(SETUP), *args],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        env={**KEINE_ANGABEN, **(env or {})},
        timeout=60,
        check=False,
    )


def test_hilfe_nennt_aufruf_und_probemodus():
    ergebnis = setup("--hilfe")
    assert ergebnis.returncode == 0
    assert "./setup.sh --lokal" in ergebnis.stdout


def test_unbekannte_option_bricht_ab():
    ergebnis = setup("--foo")
    assert ergebnis.returncode == 1
    assert "Unbekannte Option: --foo" in ergebnis.stderr


@pytest.mark.skipif(shutil.which("git") is None, reason="git fehlt")
def test_ohne_release_tag_bricht_es_mit_klarer_meldung_ab(tmp_path):
    # Eine Kopie des Repos ohne Tag: setup.sh liest Version und Tag vom Repo über sich.
    repo = tmp_path / "repo"
    (repo / "deploy").mkdir(parents=True)
    shutil.copytree(SELBST, repo / "deploy" / "selbst", ignore=shutil.ignore_patterns("data"))
    (repo / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "9.9.9"\n')
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run([*git, "init", "-q"], check=True)  # noqa: S603
    subprocess.run([*git, "add", "."], check=True)  # noqa: S603
    subprocess.run([*git, "commit", "-q", "-m", "x"], check=True)  # noqa: S603
    ergebnis = subprocess.run(  # noqa: S603
        [str(repo / "deploy" / "selbst" / "setup.sh"), "--lokal"],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        env=KEINE_ANGABEN,
        timeout=60,
        check=False,
    )
    assert ergebnis.returncode == 1
    assert "kein Release" in ergebnis.stderr
    assert "v9.9.9" in ergebnis.stderr
    assert not (repo / "deploy" / "selbst" / ".env").exists()


def test_ohne_angaben_nennt_es_alle_fehlenden_variablen():
    ergebnis = setup(env={"IMAGE_TAG": "lokal"})
    assert ergebnis.returncode == 1
    for name in (
        "DOMAIN",
        "OPERATOR_EMAILS",
        "OPERATOR_NAME",
        "OPERATOR_ADDRESS",
        "HOSTER_NAME",
        "HOSTER_ADDRESS",
        "PRIVACY_CONTACT",
    ):
        assert name in ergebnis.stderr


def test_ungueltige_domain_wird_abgelehnt():
    angaben = {
        name: "x"
        for name in (
            "OPERATOR_EMAILS",
            "OPERATOR_NAME",
            "OPERATOR_ADDRESS",
            "HOSTER_NAME",
            "HOSTER_ADDRESS",
            "PRIVACY_CONTACT",
        )
    }
    ergebnis = setup(env={"IMAGE_TAG": "lokal", "DOMAIN": "https://upload.example.org/", **angaben})
    assert ergebnis.returncode == 1
    assert "keine Domain" in ergebnis.stderr


def test_compose_der_betreiber_bleibt_getrennt():
    assert "garage" not in (SELBST.parent / "compose.yaml").read_text()
    assert "s3." not in (SELBST.parent / "Caddyfile").read_text()
