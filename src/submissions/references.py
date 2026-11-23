"""Abgabe-Kennung: kurz, lesbar, ohne verwechselbare Zeichen (kein 0/O, 1/I/L)."""

import secrets

ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
PREFIX = "SW-"
LENGTH = 4
MAX_ATTEMPTS = 50


def _draw() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))


def new_reference(exists) -> str:
    """Zieht eine Kennung, die `exists(kennung)` noch nicht kennt."""
    for _ in range(MAX_ATTEMPTS):
        reference = PREFIX + _draw()
        if not exists(reference):
            return reference
    raise RuntimeError("Keine freie Abgabe-Kennung gefunden")
