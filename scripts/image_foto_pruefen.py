"""Schickt Equipment-Fotos im gebauten Image durch `submissions.photos` (Ticket #127).

Läuft im Container, nicht im Test-Setup: Das Image kann auf einer anderen libc und mit anderen
Pillow-Wheels laufen als die Tests (Alpine/musl gegen glibc). Aufruf aus `image-pruefen.sh`:

    docker run --rm -i --entrypoint python <image> - < scripts/image_foto_pruefen.py

Je ein JPEG, PNG, WebP und HEIC mit EXIF-Beschreibung wird erzeugt und bereinigt. Es darf nichts
von der Beschreibung übrig bleiben, das Ergebnis muss ein JPEG sein, und das Thumbnail muss passen.
"""

import io
import sys

import pillow_heif
from PIL import Image

sys.path.insert(0, "/app/src")
from submissions import photos  # noqa: E402

pillow_heif.register_heif_opener()

BESCHREIBUNG = 0x010E  # EXIF ImageDescription
GEHEIM = b"GEHEIM-Beschreibung-4711"
FORMATE = ["JPEG", "PNG", "WEBP", "HEIF"]


def foto_mit_beschreibung(format_: str) -> bytes:
    bild = Image.new("RGB", (600, 400), (30, 120, 200))
    for x in range(40):
        for y in range(40):
            bild.putpixel((x, y), (255, 0, 0))  # oben links rot
    exif = Image.Exif()
    exif[BESCHREIBUNG] = GEHEIM.decode()
    out = io.BytesIO()
    bild.save(out, format=format_, exif=exif.tobytes(), quality=90)
    return out.getvalue()


fehler = []
for format_ in FORMATE:
    quelle = foto_mit_beschreibung(format_)
    with Image.open(io.BytesIO(quelle)) as vorher:
        if vorher.getexif().get(BESCHREIBUNG) != GEHEIM.decode():
            fehler.append(f"{format_}: Testdatei trägt keine Metadaten")
    try:
        sauber = photos.clean(io.BytesIO(quelle))
    except Exception as exc:  # noqa: BLE001 - jede Ausnahme ist hier ein Fund
        fehler.append(f"{format_}: {type(exc).__name__}: {exc}")
        continue
    if GEHEIM in sauber.photo or GEHEIM in sauber.thumbnail:
        fehler.append(f"{format_}: Metadaten im bereinigten Foto")
    with Image.open(io.BytesIO(sauber.photo)) as foto:
        if foto.getexif().get(BESCHREIBUNG) is not None:
            fehler.append(f"{format_}: EXIF im bereinigten Foto")
        if foto.format != "JPEG" or foto.size != (600, 400):
            fehler.append(f"{format_}: Foto ist {foto.format} {foto.size}")
        ecke = foto.convert("RGB").getpixel((10, 10))
        if ecke[0] < 200 or ecke[1] > 60:
            fehler.append(f"{format_}: Pixel stimmen nicht ({ecke})")
    with Image.open(io.BytesIO(sauber.thumbnail)) as thumb:
        if max(thumb.size) > photos.THUMBNAIL_EDGE:
            fehler.append(f"{format_}: Thumbnail zu groß {thumb.size}")
    print(f"{format_}: ok")

if fehler:
    print("Fotoprüfung im Image fehlgeschlagen:", *fehler, sep="\n  ", file=sys.stderr)
    sys.exit(1)
