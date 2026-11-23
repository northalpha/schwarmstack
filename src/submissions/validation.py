"""Prüfung eines Masters über seinen Header (ADR 0003).

Ein reines Modul: Es bekommt die ersten Bytes der Datei, ihre Größe, Endung und den Kanal und
liefert ein Ergebnis. Es kennt weder Speicher noch Datenbank.
"""

import enum
import struct
from dataclasses import dataclass
from math import prod

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import ParseError, fromstring

# So viele Bytes werden für die Prüfung gelesen (Teilabruf des Headers).
HEAD_BYTES = 1024 * 1024

_FITS_BLOCK = 2880
_CARD = 80
_XISF_SIGNATURE = b"XISF0100"
_DAMAGED = "Der Header ist unvollständig oder beschädigt."


class Category(enum.StrEnum):
    """Feste Kategorie einer Ablehnung, nach der die Statistik zählt. Der Grund bleibt Text."""

    FORMAT = "format"
    FLOAT32 = "float32"
    PLANES = "planes"
    DAMAGED = "damaged"
    SIZE = "size"
    DUPLICATE = "duplicate"

    @property
    def label(self) -> str:
        return _LABELS[self]


_LABELS = {
    Category.FORMAT: "falsches Format",
    Category.FLOAT32: "kein 32-Bit-Gleitkomma",
    Category.PLANES: "falsche Ebenen für den Kanal",
    Category.DAMAGED: "beschädigt oder unvollständig",
    Category.SIZE: "Größe weicht ab",
    Category.DUPLICATE: "Dublette in derselben Abgabe",
}


@dataclass(frozen=True)
class Result:
    ok: bool
    reason: str = ""
    category: Category | None = None


ACCEPTED = Result(True)


def rejected(category: Category, reason: str) -> Result:
    return Result(False, reason, category)


class _Rejected(Exception):
    def __init__(self, category: Category, reason: str):
        super().__init__(reason)
        self.category = category


def check(head: bytes, *, suffix: str, channel: str, channel_label: str, size: int) -> Result:
    """Prüft Format, 32-Bit-Gleitkomma und Form passend zum Kanal."""
    try:
        if size == 0 or not head:
            raise _Rejected(Category.DAMAGED, "Die Datei ist leer.")
        if suffix == ".xisf":
            planes, needed = _xisf(head)
        else:
            planes, needed = _fits(head)
        _planes_fit_channel(planes, channel, channel_label)
        if size < needed:
            raise _Rejected(Category.DAMAGED, "Die Datei ist kürzer, als ihr Header angibt.")
    except _Rejected as exc:
        return rejected(exc.category, str(exc))
    return ACCEPTED


def _planes_fit_channel(planes: int, channel: str, label: str) -> None:
    if channel == "RGB" and planes != 3:
        if planes == 1:
            raise _Rejected(Category.PLANES, "Kanal RGB, aber die Datei hat nur eine Ebene.")
        raise _Rejected(Category.PLANES, f"Kanal RGB braucht drei Ebenen, die Datei hat {planes}.")
    if channel != "RGB" and planes != 1:
        raise _Rejected(
            Category.PLANES, f"Kanal {label} braucht eine Ebene, die Datei hat {planes}."
        )


# -- FITS -------------------------------------------------------------------


def _fits(head: bytes) -> tuple[int, int]:
    """Gibt (Ebenen, Mindestgröße der Datei) zurück."""
    first = head[:_CARD].decode("ascii", "replace")
    if not first.startswith("SIMPLE  ="):
        raise _Rejected(Category.FORMAT, "Keine FITS-Datei: Der Header beginnt nicht mit SIMPLE.")
    cards = {}
    end = None
    for index in range(len(head) // _CARD):
        card = head[index * _CARD : (index + 1) * _CARD].decode("ascii", "replace")
        keyword = card[:8].strip()
        if keyword == "END":
            end = index
            break
        if card[8:10] == "= ":
            cards.setdefault(keyword, card[10:].split("/", 1)[0].strip())
    if end is None:
        raise _Rejected(Category.DAMAGED, _DAMAGED)
    if cards.get("SIMPLE") != "T":
        raise _Rejected(Category.FORMAT, "Keine standardkonforme FITS-Datei (SIMPLE ist nicht T).")

    bitpix = _int(cards.get("BITPIX"))
    if bitpix != -32:
        raise _Rejected(
            Category.FLOAT32, f"Kein 32-Bit-Gleitkomma (BITPIX = {cards.get('BITPIX', 'fehlt')})."
        )
    naxis = _int(cards.get("NAXIS"))
    if naxis not in (2, 3):
        raise _Rejected(
            Category.PLANES, f"Unerwartete Form: NAXIS = {cards.get('NAXIS', 'fehlt')}."
        )
    axes = [_int(cards.get(f"NAXIS{i}")) for i in range(1, naxis + 1)]
    if any(n is None or n <= 0 for n in axes):
        raise _Rejected(Category.DAMAGED, _DAMAGED)

    header_bytes = -(-((end + 1) * _CARD) // _FITS_BLOCK) * _FITS_BLOCK
    planes = axes[2] if naxis == 3 else 1
    return planes, header_bytes + prod(axes) * 4


def _int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


# -- XISF -------------------------------------------------------------------


def _xisf(head: bytes) -> tuple[int, int]:
    if not head.startswith(_XISF_SIGNATURE):
        raise _Rejected(Category.FORMAT, "Keine XISF-Datei: Die Signatur XISF0100 fehlt.")
    if len(head) < 16:
        raise _Rejected(Category.DAMAGED, _DAMAGED)
    (length,) = struct.unpack("<I", head[8:12])
    xml = head[16 : 16 + length]
    if len(xml) < length:
        raise _Rejected(Category.DAMAGED, _DAMAGED)
    try:
        root = fromstring(xml)
    except (ParseError, DefusedXmlException, ValueError) as exc:
        raise _Rejected(Category.DAMAGED, _DAMAGED) from exc

    image = next((el for el in root.iter() if el.tag.rsplit("}", 1)[-1] == "Image"), None)
    if image is None:
        raise _Rejected(Category.DAMAGED, _DAMAGED)
    sample = image.get("sampleFormat", "fehlt")
    if sample != "Float32":
        raise _Rejected(Category.FLOAT32, f"Kein 32-Bit-Gleitkomma (sampleFormat {sample}).")
    try:
        geometry = [int(n) for n in image.get("geometry", "").split(":")]
    except ValueError as exc:
        raise _Rejected(Category.DAMAGED, _DAMAGED) from exc
    if len(geometry) < 3 or any(n <= 0 for n in geometry):
        raise _Rejected(Category.DAMAGED, _DAMAGED)

    needed = 0
    location = image.get("location", "").split(":")
    if location[0] == "attachment":
        try:
            position, data_length = int(location[1]), int(location[2])
        except (IndexError, ValueError) as exc:
            raise _Rejected(Category.DAMAGED, _DAMAGED) from exc
        needed = position + data_length
    return geometry[-1], needed
