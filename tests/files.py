"""Erzeugt kleine XISF- und FITS-Dateien für Tests."""

import struct
from xml.sax.saxutils import escape, quoteattr

BLOCK = 2880


def card(keyword, value=None, comment=""):
    """Eine FITS-Karte. Ohne Wert eine Kommentarkarte (COMMENT, HISTORY, CONTINUE, leer)."""
    if value is None:
        return f"{keyword:<8}{comment}"[:80].ljust(80)
    if isinstance(value, bool):
        text = f"{'T' if value else 'F':>20}"
    elif isinstance(value, str):
        text = ("'" + value.replace("'", "''").ljust(8) + "'").ljust(20)
    else:
        text = f"{value:>20}"
    line = f"{keyword:<8}= {text}"
    if comment:
        line += f" / {comment}"
    return line[:80].ljust(80)


def _header(cards):
    header = "".join(c.ljust(80) for c in cards).encode("ascii")
    return header + b" " * (-len(header) % BLOCK)


def fits(width=4, height=3, planes=None, *, bitpix=-32, simple="T", truncate=0, end=True,
         keywords=(), extension=None):  # fmt: skip
    """`keywords`: weitere Karten als (Schlüssel, Wert, Kommentar) vor END.

    `extension`: Karten einer zweiten HDU (IMAGE ohne Daten) nach den Pixeldaten.
    """
    axes = [width, height] + ([planes] if planes is not None else [])
    cards = [
        f"SIMPLE  = {simple:>20}",
        f"BITPIX  = {bitpix:>20}",
        f"NAXIS   = {len(axes):>20}",
        *(f"NAXIS{i}  = {n:>20}" for i, n in enumerate(axes, start=1)),
        *(card(*k) for k in keywords),
    ]
    if end:
        cards.append("END")
    header = _header(cards)
    count = 1
    for n in axes:
        count *= n
    data = b"\0" * (count * abs(bitpix) // 8)
    data += b"\0" * (-len(data) % BLOCK)
    blob = header + data
    if extension is not None:
        blob += _header(
            [
                card("XTENSION", "IMAGE"),
                card("BITPIX", -32),
                card("NAXIS", 0),
                card("PCOUNT", 0),
                card("GCOUNT", 1),
                *(card(*k) for k in extension),
                "END",
            ]
        )
    return blob[: len(blob) - truncate] if truncate else blob


def xisf(width=4, height=3, channels=1, *, sample="Float32", truncate=0, signature=b"XISF0100",
         xml=None, fits_keywords=(), properties=(), metadata=()):  # fmt: skip
    """`fits_keywords`: (Name, Wert, Kommentar) im <Image>.

    `properties` (im <Image>) und `metadata` (im <Metadata>): (id, Typ, Wert).
    """
    color = "RGB" if channels == 3 else "Gray"
    data_length = width * height * channels * 4
    position = 4096  # Daten beginnen nach dem Header, an fester Stelle
    if xml is None:
        inner = "".join(
            f"<FITSKeyword name={quoteattr(n)} value={quoteattr(v)} comment={quoteattr(c)}/>"
            for n, v, c in fits_keywords
        ) + "".join(_property(*p) for p in properties)
        meta = "".join(_property(*p) for p in metadata)
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<xisf version="1.0" xmlns="http://www.pixinsight.com/xisf">'
            f'<Image geometry="{width}:{height}:{channels}" sampleFormat="{sample}" '
            f'colorSpace="{color}" location="attachment:{position}:{data_length}">{inner}</Image>'
            + (f"<Metadata>{meta}</Metadata>" if meta else "")
            + "</xisf>"
        )
    header = signature + struct.pack("<I", len(xml.encode())) + b"\0" * 4 + xml.encode()
    assert len(header) <= position, "XML passt nicht vor die Daten"  # noqa: S101
    blob = header.ljust(position, b"\0") + b"\0" * data_length
    return blob[: len(blob) - truncate] if truncate else blob


def _property(id_, type_, value):
    if type_ == "String":
        return f"<Property id={quoteattr(id_)} type={quoteattr(type_)}>{escape(value)}</Property>"
    return f"<Property id={quoteattr(id_)} type={quoteattr(type_)} value={quoteattr(value)}/>"
