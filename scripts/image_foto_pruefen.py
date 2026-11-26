"""Schickt Equipment-Fotos im gebauten Image durch `submissions.photos` (Ticket #127).

Läuft im Container, nicht im Test-Setup: Das Image kann auf einer anderen libc und mit anderen
Pillow-Wheels laufen als die Tests (Alpine/musl gegen glibc). Aufruf aus `image-pruefen.sh`:

    docker run --rm -i --entrypoint python <image> - < scripts/image_foto_pruefen.py

Je ein JPEG, PNG, WebP und HEIC mit EXIF-Standort wird erzeugt und bereinigt. Es darf nichts
vom Standort übrig bleiben, das Ergebnis muss ein JPEG sein, und das Thumbnail muss passen.
"""

import io
import sys

import pillow_heif
from PIL import Image

sys.path.insert(0, "/app/src")
from submissions import photos  # noqa: E402

pillow_heif.register_heif_opener()

GEHEIM = b"GEHEIM-Standort-4711"
FORMATE = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp", "HEIF": "image/heic"}


def beispiel(format_: str) -> bytes:
    bild = Image.new("RGB", (600, 400), (30, 120, 200))
    for x in range(40):
        for y in range(40):
            bild.putpixel((x, y), (255, 0, 0))  # oben links rot
    exif = Image.Exif()
    exif[0x010E] = GEHEIM.decode()  # ImageDescription
    out = io.BytesIO()
    bild.save(out, format=format_, exif=exif.tobytes(), quality=90)
    return out.getvalue()


fehler = []
for format_ in FORMATE:
    quelle = beispiel(format_)
    if format_ != "PNG" and GEHEIM not in quelle:
        # PNG und HEIC speichern EXIF anders; hier zählt nur, dass die Quelle Metadaten trägt.
        if format_ in ("JPEG", "WEBP"):
            fehler.append(f"{format_}: Testdatei trägt keine Metadaten")
    try:
        sauber = photos.clean(io.BytesIO(quelle))
    except Exception as exc:  # noqa: BLE001 - jede Ausnahme ist hier ein Fund
        fehler.append(f"{format_}: {type(exc).__name__}: {exc}")
        continue
    if GEHEIM in sauber.photo or GEHEIM in sauber.thumbnail:
        fehler.append(f"{format_}: Metadaten im bereinigten Foto")
    with Image.open(io.BytesIO(sauber.photo)) as foto:
        if foto.format != "JPEG" or foto.size != (600, 400):
            fehler.append(f"{format_}: Foto ist {foto.format} {foto.size}")
        rot = foto.convert("RGB").getpixel((10, 10))
        if rot[0] < 200 or rot[1] > 60:
            fehler.append(f"{format_}: Pixel stimmen nicht ({rot})")
    with Image.open(io.BytesIO(sauber.thumbnail)) as thumb:
        if max(thumb.size) > photos.THUMBNAIL_EDGE:
            fehler.append(f"{format_}: Thumbnail zu groß {thumb.size}")
    print(f"{format_}: ok")

if fehler:
    print("Fotoprüfung im Image fehlgeschlagen:", *fehler, sep="\n  ", file=sys.stderr)
    sys.exit(1)
