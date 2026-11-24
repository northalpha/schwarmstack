"""Views, API und Admin schreiben nichts selbst: Schreibzugriffe liegen in services/uploads.

Mechanischer Teil der Regel „Wo Fachverhalten liegt“ in CODING_STANDARDS.md. Ob eine
Bedingung („darf das jetzt?“) Fachverhalten ist, bleibt ein Urteil im Review.
"""

import ast
from pathlib import Path

import pytest

SUBMISSIONS = Path(__file__).parent.parent / "src" / "submissions"
OBERFLAECHEN = ["views.py", "api.py", "admin.py"]
SCHREIBEND = {
    "save",
    "update",
    "delete",
    "create",
    "get_or_create",
    "update_or_create",
    "bulk_create",
    "bulk_update",
}
# (Datei, Zeile) mit begründeter Ausnahme; leer lassen, solange es geht.
AUSNAHMEN: set[tuple[str, int]] = set()


@pytest.mark.parametrize("datei", OBERFLAECHEN)
def test_oberflaechen_schreiben_nicht_selbst(datei):
    baum = ast.parse((SUBMISSIONS / datei).read_text())
    treffer = [
        f"{datei}:{knoten.lineno} .{knoten.func.attr}()"
        for knoten in ast.walk(baum)
        if isinstance(knoten, ast.Call)
        and isinstance(knoten.func, ast.Attribute)
        and knoten.func.attr in SCHREIBEND
        and (datei, knoten.lineno) not in AUSNAHMEN
    ]
    assert not treffer, (
        "Schreibzugriff in der Oberfläche; die Regel gehört nach services.py oder uploads.py "
        "(CODING_STANDARDS.md, „Wo Fachverhalten liegt“): " + ", ".join(treffer)
    )
