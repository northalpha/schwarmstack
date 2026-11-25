"""Erzeugt Equipment-Fotos für Tests: je Format vollständig mit Metadaten bestückt.

Jedes Foto trägt GPS-Koordinaten, Seriennummern, Zeitstempel, XMP, IPTC (nur JPEG), einen
Kommentar, ein ICC-Profil und ein eingebettetes Miniaturbild im EXIF. Die Fundstellen stehen in
`GEHEIM`: Texte, die nach der Bereinigung in keinem Byte der Datei mehr vorkommen dürfen.
"""

import io
import struct

import piexif
import pillow_heif
from PIL import Image, ImageCms

pillow_heif.register_heif_opener()

FORMATE = ["jpeg", "png", "webp", "heic"]
WIDTH, HEIGHT = 96, 64

# Eindeutige Texte, die in den Metadaten stehen. Nach der Bereinigung darf keiner mehr in der
# Datei vorkommen, in keiner Kodierung.
GEHEIM = [
    "Kamera-Hersteller-GEHEIM",
    "Modell-GEHEIM",
    "SN-GEHEIM-4711",
    "Objektiv-SN-GEHEIM",
    "Beschreibung-GEHEIM",
    "Autor-GEHEIM",
    "Kommentar-GEHEIM",
    "2019:03:14 22:15:09",
    "XMP-GEHEIM-Strasse",
    "IPTC-GEHEIM-Ort",
    "Software-GEHEIM",
    "sRGB built-in",
]
GEHEIM_BYTES = [text.encode() for text in GEHEIM] + [text.encode("utf-16-le") for text in GEHEIM]


def pixels(width=WIDTH, height=HEIGHT) -> Image.Image:
    """Ein Bild mit Verlauf und einem Eckpunkt, damit Drehung und Spiegelung auffallen."""
    image = Image.new("RGB", (width, height))
    image.putdata(
        [
            (x * 255 // (width - 1), y * 255 // (height - 1), 128)
            for y in range(height)
            for x in range(width)
        ]
    )
    for x in range(8):
        for y in range(8):
            image.putpixel((x, y), (255, 0, 0))  # oben links rot
    return image


def _rational(value, scale=1000):
    return (int(value * scale), scale)


def exif(*, orientation=1, width=WIDTH, height=HEIGHT) -> bytes:
    thumbnail = io.BytesIO()
    pixels(16, 12).save(thumbnail, "JPEG")
    return piexif.dump(
        {
            "0th": {
                piexif.ImageIFD.Make: b"Kamera-Hersteller-GEHEIM",
                piexif.ImageIFD.Model: b"Modell-GEHEIM",
                piexif.ImageIFD.Software: b"Software-GEHEIM",
                piexif.ImageIFD.ImageDescription: b"Beschreibung-GEHEIM",
                piexif.ImageIFD.Artist: b"Autor-GEHEIM",
                piexif.ImageIFD.Orientation: orientation,
                piexif.ImageIFD.DateTime: b"2019:03:14 22:15:09",
            },
            "Exif": {
                piexif.ExifIFD.DateTimeOriginal: b"2019:03:14 22:15:09",
                piexif.ExifIFD.BodySerialNumber: b"SN-GEHEIM-4711",
                piexif.ExifIFD.LensSerialNumber: b"Objektiv-SN-GEHEIM",
                piexif.ExifIFD.UserComment: b"ASCII\x00\x00\x00Kommentar-GEHEIM",
                piexif.ExifIFD.MakerNote: b"Kamera-Hersteller-GEHEIM\x00" + bytes(range(32)),
            },
            "GPS": {
                piexif.GPSIFD.GPSLatitudeRef: b"N",
                piexif.GPSIFD.GPSLatitude: (_rational(52), _rational(31), _rational(12.345)),
                piexif.GPSIFD.GPSLongitudeRef: b"E",
                piexif.GPSIFD.GPSLongitude: (_rational(13), _rational(24), _rational(5.678)),
                piexif.GPSIFD.GPSAltitude: (3412, 100),
            },
            "1st": {
                piexif.ImageIFD.Compression: 6,
                piexif.ImageIFD.XResolution: (72, 1),
                piexif.ImageIFD.YResolution: (72, 1),
            },
            "thumbnail": thumbnail.getvalue(),
        }
    )


XMP = (
    b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/'
    b'22-rdf-syntax-ns#"><rdf:Description xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/"'
    b' xmlns:exif="http://ns.adobe.com/exif/1.0/" photoshop:City="XMP-GEHEIM-Strasse"'
    b' exif:GPSLatitude="52,31.2057N" exif:GPSLongitude="13,24.0946E"/></rdf:RDF></x:xmpmeta>'
    b'<?xpacket end="w"?>'
)


def _icc() -> bytes:
    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def _iptc() -> bytes:
    """Ein IPTC-Block (Photoshop-Ressource 0x0404) mit Ort und Stichwort."""

    def dataset(number, text):
        return b"\x1c\x02" + bytes([number]) + struct.pack(">H", len(text)) + text

    iptc = dataset(90, b"IPTC-GEHEIM-Ort") + dataset(25, b"IPTC-GEHEIM-Ort")
    if len(iptc) % 2:
        iptc += b"\x00"
    return b"Photoshop 3.0\x008BIM\x04\x04\x00\x00" + struct.pack(">I", len(iptc)) + iptc


def _insert_app13(jpeg: bytes) -> bytes:
    payload = _iptc()
    segment = b"\xff\xed" + struct.pack(">H", len(payload) + 2) + payload
    return jpeg[:2] + segment + jpeg[2:]


def foto(format: str, *, orientation=1, with_metadata=True, size=(WIDTH, HEIGHT)) -> bytes:
    """Ein Foto im gewünschten Eingabeformat, mit allen Metadaten, die das Format kennt."""
    image = pixels(*size)
    meta = (
        {
            "exif": exif(orientation=orientation, width=size[0], height=size[1]),
            "icc_profile": _icc(),
        }
        if with_metadata
        else {}
    )
    out = io.BytesIO()
    if format == "jpeg":
        extra = {"xmp": XMP, "comment": b"Kommentar-GEHEIM"} if with_metadata else {}
        image.save(out, "JPEG", quality=95, subsampling=0, **meta, **extra)
        return _insert_app13(out.getvalue()) if with_metadata else out.getvalue()
    if format == "png":
        from PIL.PngImagePlugin import PngInfo

        info = PngInfo()
        if with_metadata:
            info.add_text("Comment", "Kommentar-GEHEIM")
            info.add_itxt("XML:com.adobe.xmp", XMP.decode(), zip=False)
            info.add_text("Author", "Autor-GEHEIM", zip=True)
        image.save(out, "PNG", pnginfo=info, **meta)
    elif format == "webp":
        extra = {"xmp": XMP} if with_metadata else {}
        image.save(out, "WEBP", lossless=True, **meta, **extra)
    elif format == "heic":
        extra = {"xmp": XMP} if with_metadata else {}
        image.save(out, "HEIF", quality=-1, **meta, **extra)  # -1: verlustfrei
    else:
        raise ValueError(format)
    return out.getvalue()
