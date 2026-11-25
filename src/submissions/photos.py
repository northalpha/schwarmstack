"""Equipment-Foto bereinigen (Ticket #82, ADR 0005).

Das Foto läuft durch den Server und wird nie so gespeichert, wie es kam: Das Bild wird
dekodiert und nur seine Pixel werden in ein festes Ausgabeformat (JPEG) neu geschrieben. Eine
Sperrliste von Metadaten-Feldern gibt es bewusst nicht; was nicht Pixel ist, geht nie in die
neue Datei, auch wenn das Format morgen ein neues Feld kennt (EXIF mit Standort, XMP, IPTC,
Kommentare, Farbprofil-Texte, eingebettetes Miniaturbild).

Die Bildverarbeitung ist Pillow mit pillow-heif für HEIC. Metadaten werden hier nirgends
gelesen, protokolliert oder in Fehlermeldungen genannt; der Dateiname der Teilnehmenden kommt
in dieses Modul gar nicht hinein. Das Thumbnail entsteht aus dem bereits bereinigten Bild.
"""

import io
import struct
from dataclasses import dataclass
from typing import BinaryIO

import pillow_heif
from PIL import Image, ImageOps

pillow_heif.register_heif_opener()

MAX_BYTES = 10 * 1024**2
# Längste Kante des gespeicherten Fotos; größere Bilder werden verkleinert.
MAX_EDGE = 4096
# Längste Kante des Thumbnails: doppelte Breite der Karte in der Seitenleiste (252 px).
THUMBNAIL_EDGE = 504
# Obergrenze der Pixelzahl, geprüft vor dem Dekodieren (Dekompressionsbombe); gilt für alle Formate.
MAX_PIXELS = 64_000_000
# Eingabeformate: nur diese vier Decoder dürfen eine Datei lesen.
INPUT_FORMATS = ["JPEG", "PNG", "WEBP", "HEIF"]
QUALITY = 90

# Ausnahmen, mit denen Pillow und pillow-heif kaputte Dateien melden.
_DECODE_ERRORS = (
    OSError,  # auch UnidentifiedImageError und abgeschnittene Dateien
    ValueError,  # auch pillow-heif (HeifError)
    SyntaxError,  # Pillows Decoder für beschädigte PNG-Chunks
    EOFError,
    struct.error,
    Image.DecompressionBombError,
)


class PhotoRejected(Exception):
    """Das Foto wird abgelehnt; die Meldung ist für die Teilnehmenden gedacht."""


@dataclass(frozen=True)
class CleanPhoto:
    photo: bytes
    thumbnail: bytes


def clean(source: BinaryIO) -> CleanPhoto:
    """Dekodiert das Foto und schreibt nur die Pixel neu: das Foto und sein Thumbnail.

    Wirft `PhotoRejected` bei zu großer, kaputter oder nicht unterstützter Datei; es gibt
    keinen Weg, auf dem die Originaldatei durchgereicht wird.
    """
    data = source.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise PhotoRejected("Das Foto ist größer als 10 MB.")
    try:
        with Image.open(io.BytesIO(data), formats=INPUT_FORMATS) as image:
            if image.width * image.height > MAX_PIXELS:
                raise PhotoRejected("Das Foto hat zu viele Pixel.")
            image.draft("RGB", (MAX_EDGE, MAX_EDGE))  # JPEG: gleich verkleinert dekodieren
            image.load()  # nur das erste Bild
            pixels = _pixels_only(ImageOps.exif_transpose(image))
    except PhotoRejected:
        raise
    except _DECODE_ERRORS:
        # Fehlertext und Ursache der Bibliothek bleiben draußen: Sie könnten Inhalte der Datei
        # nennen und landeten sonst im Protokoll.
        raise PhotoRejected(
            "Das Foto lässt sich nicht lesen. Erlaubt sind JPEG, PNG, WebP und HEIC."
        ) from None

    pixels.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
    thumbnail = pixels.copy()
    thumbnail.thumbnail((THUMBNAIL_EDGE, THUMBNAIL_EDGE), Image.Resampling.LANCZOS)
    return CleanPhoto(photo=_jpeg(pixels), thumbnail=_jpeg(thumbnail))


def _pixels_only(image: Image.Image) -> Image.Image:
    """Ein neues Bild nur aus den Pixeln: ohne `info`, EXIF, Farbprofil und alles andere."""
    if image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info:
        rgba = image.convert("RGBA")
        white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        image = Image.alpha_composite(white, rgba).convert("RGB")
    elif image.mode.startswith(("I", "F")):  # 16 Bit und mehr: auf 8 Bit herunterrechnen
        image = image.point(lambda value: value * (1 / 256)).convert("L")
    elif image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    return Image.frombytes(image.mode, image.size, image.tobytes())


def _jpeg(image: Image.Image) -> bytes:
    out = io.BytesIO()
    # Ohne `exif`, `icc_profile`, `xmp` und `comment`: Das Bild hat nichts davon mitgenommen.
    image.save(out, "JPEG", quality=QUALITY, optimize=True)
    return out.getvalue()
