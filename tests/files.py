"""Erzeugt kleine XISF- und FITS-Dateien für Tests."""

import struct

BLOCK = 2880


def fits(width=4, height=3, planes=None, *, bitpix=-32, simple="T", truncate=0, end=True):
    axes = [width, height] + ([planes] if planes is not None else [])
    cards = [
        f"SIMPLE  = {simple:>20}",
        f"BITPIX  = {bitpix:>20}",
        f"NAXIS   = {len(axes):>20}",
        *(f"NAXIS{i}  = {n:>20}" for i, n in enumerate(axes, start=1)),
    ]
    if end:
        cards.append("END")
    header = "".join(card.ljust(80) for card in cards).encode("ascii")
    header += b" " * (-len(header) % BLOCK)
    count = 1
    for n in axes:
        count *= n
    data = b"\0" * (count * abs(bitpix) // 8)
    data += b"\0" * (-len(data) % BLOCK)
    blob = header + data
    return blob[: len(blob) - truncate] if truncate else blob


def xisf(width=4, height=3, channels=1, *, sample="Float32", truncate=0, signature=b"XISF0100",
         xml=None):  # fmt: skip
    color = "RGB" if channels == 3 else "Gray"
    data_length = width * height * channels * 4
    position = 4096  # Daten beginnen nach dem Header, an fester Stelle
    if xml is None:
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<xisf version="1.0" xmlns="http://www.pixinsight.com/xisf">'
            f'<Image geometry="{width}:{height}:{channels}" sampleFormat="{sample}" '
            f'colorSpace="{color}" location="attachment:{position}:{data_length}"/>'
            "</xisf>"
        )
    header = signature + struct.pack("<I", len(xml.encode())) + b"\0" * 4 + xml.encode()
    blob = header.ljust(position, b"\0") + b"\0" * data_length
    return blob[: len(blob) - truncate] if truncate else blob
