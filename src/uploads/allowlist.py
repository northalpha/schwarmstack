"""Erlaubte Dateiendungen. Fest verdrahtet, bewusst nicht per Admin erweiterbar."""

import os

FORMAT_BY_EXTENSION = {
    ".fits": "fits",
    ".fit": "fits",
    ".fts": "fits",
    ".xisf": "xisf",
}


def allowed_format(filename: str) -> str | None:
    """'fits' oder 'xisf' anhand der Endung (ohne Groß-/Kleinschreibung), sonst None."""
    return FORMAT_BY_EXTENSION.get(os.path.splitext(filename or "")[1].lower())
