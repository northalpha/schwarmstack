"""Equipment-Foto: Bildbereinigung ohne Metadaten, Orientierung, Grenzen (Ticket #82).

Geprüft wird über die Bytes der entstandenen Dateien, nicht über die Bibliothek, die sie schreibt.
"""

import io
import struct

import pytest
from photo_files import FORMATE, GEHEIM_BYTES, HEIGHT, WIDTH, foto, pixels
from PIL import Image, ImageChops, ImageStat

from submissions import photos

# Segmente, die in einer bereinigten JPEG-Datei vorkommen dürfen: nur das, was Pixel beschreibt.
# SOI, JFIF, DQT, SOF, DHT, SOS, EOI, DRI
ERLAUBT = {
    0xD8,
    0xE0,
    0xDB,
    0xC0,
    0xC2,
    0xC4,
    0xDA,
    0xD9,
    0xDD,
}


def segmente(jpeg: bytes) -> list[int]:
    """Alle Marker einer JPEG-Datei bis zum Start der Bilddaten."""
    assert jpeg[:2] == b"\xff\xd8"
    marker, position = [0xD8], 2
    while position < len(jpeg):
        assert jpeg[position] == 0xFF
        code = jpeg[position + 1]
        marker.append(code)
        if code == 0xDA:  # Bilddaten ab hier
            break
        position += 2 + struct.unpack(">H", jpeg[position + 2 : position + 4])[0]
    return marker


def assert_ohne_metadaten(data: bytes):
    for text in GEHEIM_BYTES:
        assert text not in data, text
    assert segmente(data)[:-1] and set(segmente(data)) <= ERLAUBT, segmente(data)
    for kennung in (b"Exif", b"xap", b"Photoshop", b"ICC_PROFILE", b"8BIM", b"GPS"):
        assert kennung not in data, kennung
    with Image.open(io.BytesIO(data)) as image:
        assert image.format == "JPEG"
        assert len(image.getexif()) == 0
        assert not (
            set(image.info)
            - {
                "jfif",
                "jfif_version",
                "jfif_unit",
                "jfif_density",
                "dpi",
                "progressive",
                "progression",
            }
        )


def abweichung(a: Image.Image, b: Image.Image) -> float:
    """Mittlere Abweichung je Kanal (0 bis 255) zwischen zwei gleich großen Bildern."""
    assert a.size == b.size
    return sum(ImageStat.Stat(ImageChops.difference(a.convert("RGB"), b.convert("RGB"))).mean) / 3


@pytest.mark.parametrize("format", FORMATE)
def test_foto_und_thumbnail_enthalten_keine_metadaten(format):
    original = foto(format)
    ergebnis = photos.clean(io.BytesIO(original))
    assert_ohne_metadaten(ergebnis.photo)
    assert_ohne_metadaten(ergebnis.thumbnail)


@pytest.mark.parametrize("format", FORMATE)
def test_pixel_stimmen_mit_dem_original_ueberein(format):
    ergebnis = photos.clean(io.BytesIO(foto(format)))
    with Image.open(io.BytesIO(ergebnis.photo)) as bereinigt:
        assert bereinigt.size == (WIDTH, HEIGHT)
        assert abweichung(bereinigt, pixels()) < 3  # nur das Neukodieren


@pytest.mark.parametrize("format", FORMATE)
def test_orientierung_wird_vor_dem_verwerfen_angewendet(format):
    # EXIF-Orientierung 6: Das Bild ist zum Anzeigen um 90° im Uhrzeigersinn zu drehen.
    ergebnis = photos.clean(io.BytesIO(foto(format, orientation=6)))
    with Image.open(io.BytesIO(ergebnis.photo)) as bereinigt:
        assert bereinigt.size == (HEIGHT, WIDTH)
        assert abweichung(bereinigt, pixels().transpose(Image.Transpose.ROTATE_270)) < 3
    assert_ohne_metadaten(ergebnis.photo)


def test_thumbnail_hat_laengste_kante_504_und_das_seitenverhaeltnis():
    ergebnis = photos.clean(io.BytesIO(foto("png", size=(1200, 800))))
    with Image.open(io.BytesIO(ergebnis.thumbnail)) as thumbnail:
        assert thumbnail.size == (504, 336)
    with Image.open(io.BytesIO(ergebnis.photo)) as bereinigt:
        assert bereinigt.size == (1200, 800)


def test_kleines_foto_wird_fuers_thumbnail_nicht_vergroessert():
    ergebnis = photos.clean(io.BytesIO(foto("png")))
    with Image.open(io.BytesIO(ergebnis.thumbnail)) as thumbnail:
        assert thumbnail.size == (WIDTH, HEIGHT)


def test_grosse_kantenlaenge_wird_auf_4096_verkleinert():
    gross = io.BytesIO()
    Image.new("L", (5000, 1000), 90).save(gross, "PNG")
    ergebnis = photos.clean(io.BytesIO(gross.getvalue()))
    with Image.open(io.BytesIO(ergebnis.photo)) as bereinigt:
        assert bereinigt.size == (4096, 819)


def test_transparenz_und_paletten_werden_zu_rgb():
    daten = io.BytesIO()
    Image.new("RGBA", (10, 10), (255, 0, 0, 0)).save(daten, "PNG")  # ganz durchsichtig
    ergebnis = photos.clean(io.BytesIO(daten.getvalue()))
    with Image.open(io.BytesIO(ergebnis.photo)) as bereinigt:
        assert bereinigt.convert("RGB").getpixel((5, 5)) == (255, 255, 255)  # auf Weiß gelegt
    daten = io.BytesIO()
    Image.new("P", (10, 10), 3).save(daten, "PNG")
    photos.clean(io.BytesIO(daten.getvalue()))


def test_nur_das_erste_bild_zaehlt():
    daten = io.BytesIO()
    rot = Image.new("RGB", (16, 16), (255, 0, 0))
    rot.save(
        daten,
        "WEBP",
        lossless=True,
        save_all=True,
        append_images=[Image.new("RGB", (16, 16), (0, 0, 255))],
    )
    ergebnis = photos.clean(io.BytesIO(daten.getvalue()))
    with Image.open(io.BytesIO(ergebnis.photo)) as bereinigt:
        assert abweichung(bereinigt, rot) < 3


def test_zu_grosse_datei_wird_vor_dem_dekodieren_abgelehnt(monkeypatch):
    def nie(*args, **kwargs):
        raise AssertionError("dekodiert")

    monkeypatch.setattr(photos.Image, "open", nie)
    with pytest.raises(photos.PhotoRejected, match="10 MB"):
        photos.clean(io.BytesIO(b"x" * (photos.MAX_BYTES + 1)))


@pytest.mark.parametrize(
    "daten",
    [
        b"",
        b"kein Bild",
        b"GIF89a" + bytes(40),  # bekanntes, aber nicht erlaubtes Format
        b"%PDF-1.7\n" + bytes(100),
    ],
)
def test_kaputte_und_nicht_unterstuetzte_dateien_werden_abgelehnt(daten):
    with pytest.raises(photos.PhotoRejected):
        photos.clean(io.BytesIO(daten))


@pytest.mark.parametrize("format", FORMATE)
def test_abgeschnittene_dateien_werden_abgelehnt(format):
    original = foto(format)
    # Bei HEIC stehen Exif und XMP hinter den Bilddaten: Fehlt nur das Ende, sind die Pixel
    # vollständig und das Foto ist lesbar.
    for laenge in (len(original) // 2, *(() if format == "heic" else (len(original) - 40,))):
        with pytest.raises(photos.PhotoRejected):
            photos.clean(io.BytesIO(original[:laenge]))


@pytest.mark.parametrize("format", ["png", "webp"])
def test_pixelbombe_wird_abgelehnt(format, monkeypatch):
    monkeypatch.setattr(photos, "MAX_PIXELS", 10_000)
    daten = io.BytesIO()
    Image.new("L", (200, 200), 0).save(daten, format)
    with pytest.raises(photos.PhotoRejected, match="Pixel"):
        photos.clean(io.BytesIO(daten.getvalue()))


def test_pixelbombe_im_jpeg_und_heic_wird_abgelehnt(monkeypatch):
    monkeypatch.setattr(photos, "MAX_PIXELS", 5_000)
    for format in ("jpeg", "heic"):
        with pytest.raises(photos.PhotoRejected, match="Pixel"):
            photos.clean(io.BytesIO(foto(format)))  # 96 x 64 = 6144 Pixel


def test_fehlermeldung_nennt_weder_dateinamen_noch_metadaten():
    original = foto("jpeg")[:200]

    class Datei(io.BytesIO):
        name = "Garten-Musterstrasse-12.jpg"

    with pytest.raises(photos.PhotoRejected) as fehler:
        photos.clean(Datei(original))
    text = str(fehler.value)
    assert "Musterstrasse" not in text
    assert not any(geheim.decode(errors="ignore") in text for geheim in GEHEIM_BYTES)
