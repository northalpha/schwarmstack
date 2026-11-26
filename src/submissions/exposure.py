"""Belichtungsangaben eines Masters: aus dem Header lesen und fehlende Werte vorschlagen (ADR 0010).

Ein reines Modul wie `validation`: Es bekommt die ersten Bytes der Datei bzw. die gespeicherten
Werte eines Masters und kennt weder Speicher noch Datenbankabfragen.

Gelesen wird nur eine Whitelist von Schlüsseln. Standort- und Personendaten (`SITELAT`,
`SITELONG`, `OBSGEO-*`, `OBSERVER`) werden nicht einmal gelesen, und der Header wird nie als
Ganzes gespeichert.
"""

import enum
import re
import struct
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import ParseError, fromstring
from django.db import models

TEXT_LENGTH = 100
# Sekunden: bis 4 Nachkommastellen, unter 10^10 s (passt zu den Modellfeldern).
SECONDS_PLACES = Decimal("0.0001")
SECONDS_MAX = Decimal(10) ** 10

PER_LIGHT = "exposure_per_light"
COUNT = "light_count"
TOTAL = "total_exposure"
INSTRUMENT = "instrument"
TELESCOPE = "telescope"
NUMBERS = (PER_LIGHT, COUNT, TOTAL)
FIELDS = (*NUMBERS, INSTRUMENT, TELESCOPE)


class Source(models.TextChoices):
    """Herkunft eines Werts der Belichtungsangaben."""

    HEADER = "header", "Header"
    COMPUTED = "berechnet", "berechnet"
    MANUAL = "manuell", "manuell"


class Meaning(enum.Enum):
    """Was `EXPTIME` bei einem Erzeuger bedeutet."""

    TOTAL = TOTAL
    PER_LIGHT = PER_LIGHT


# Erzeuger -> Bedeutung von EXPTIME. Verglichen wird der Anfang, ohne Groß-/Kleinschreibung.
# Siril und PixInsight fehlen bewusst, bis echte Master sie belegen (#63).
EXPTIME_MEANING = {"DWARFLAB": Meaning.TOTAL}

# Whitelist: FITS-Keyword -> XISF-Property mit derselben Bedeutung (None: keine).
_FITS_TO_XISF = {
    "EXPTIME": "Instrument:ExposureTime",
    "STACKCNT": None,
    "LIVETIME": None,
    "INSTRUME": "Instrument:Camera:Name",
    "TELESCOP": "Instrument:Telescope:Name",
    "ORIGIN": None,
    "SWCREATE": None,
    # Filtername (#95): `FILT-1` und `INSFLNAM` sind Aliase von `FILTER`.
    "FILTER": "Instrument:Filter:Name",
    "FILT-1": None,
    "INSFLNAM": None,
}
_FILTER_KEYS = ("FILTER", "FILT-1", "INSFLNAM")
_CREATOR_PROPERTY = "XISF:CreatorApplication"
_XISF_PROPERTIES = {p for p in _FITS_TO_XISF.values() if p} | {_CREATOR_PROPERTY}
# Diese Schlüssel werden auf Widersprüche zwischen XISF-Property und FITS-Keyword geprüft.
_CONFLICT_KEYS = ("EXPTIME", "INSTRUME", "TELESCOP", "FILTER")
# Zu welchen Feldern ein Widerspruch gehört; ist eines davon von Hand gesetzt, ist er erledigt.
_CONFLICT_FIELDS = {
    "EXPTIME": (PER_LIGHT, TOTAL),
    "INSTRUME": (INSTRUMENT,),
    "TELESCOP": (TELESCOPE,),
    "FILTER": (),  # der Kanal wird beim Upload von Hand gewählt; der Widerspruch bleibt sichtbar
}

_CARD = 80
_XISF_SIGNATURE = b"XISF0100"


@dataclass(frozen=True)
class HeaderValues:
    """Die Werte der Whitelist, wie sie im Header stehen (Text), ohne Deutung."""

    keywords: dict[str, str] = field(default_factory=dict)
    creators: tuple[str, ...] = ()
    # Schlüssel -> abweichender Wert des FITS-Keywords, wenn eine XISF-Property Vorrang hatte.
    conflicts: dict[str, str] = field(default_factory=dict)


def read(head: bytes, suffix: str) -> HeaderValues:
    """Liest die Whitelist aus dem Anfang der Datei. Wirft nie: Ein kaputter Header ergibt
    einfach keine Werte (die Prüfung hat ihn vorher schon beurteilt)."""
    try:
        if suffix == ".xisf":
            return _read_xisf(head)
        return _read_fits(head)
    except (ParseError, DefusedXmlException, ValueError, struct.error):
        return HeaderValues()


# -- FITS -------------------------------------------------------------------


def _fits_cards(head: bytes, wanted) -> dict[str, str]:
    """Die ersten Karten mit diesen Schlüsseln aus der primären HDU, bis END."""
    found: dict[str, str] = {}
    for index in range(len(head) // _CARD):
        card = head[index * _CARD : (index + 1) * _CARD].decode("ascii", "replace")
        keyword = card[:8].strip()
        if keyword == "END":
            break
        if keyword in wanted and keyword not in found and card[8:10] == "= ":
            found[keyword] = _card_value(card[10:])
    return found


def _card_value(rest: str) -> str:
    """Wert einer FITS-Karte ohne Kommentar; Text ohne Anführungszeichen."""
    rest = rest.strip()
    if not rest.startswith("'"):
        return rest.split("/", 1)[0].strip()
    value, i = [], 1
    while i < len(rest):
        if rest[i] == "'":
            if rest[i + 1 : i + 2] == "'":
                value.append("'")
                i += 2
                continue
            break
        value.append(rest[i])
        i += 1
    return "".join(value).strip()


def _read_fits(head: bytes) -> HeaderValues:
    keywords = _fits_cards(head, _FITS_TO_XISF)
    creators = tuple(keywords[k] for k in ("SWCREATE", "ORIGIN") if keywords.get(k))
    return HeaderValues(keywords=keywords, creators=creators)


# -- XISF -------------------------------------------------------------------


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _read_xisf(head: bytes) -> HeaderValues:
    if not head.startswith(_XISF_SIGNATURE) or len(head) < 16:
        return HeaderValues()
    (length,) = struct.unpack("<I", head[8:12])
    root = fromstring(head[16 : 16 + length])

    fits_keywords: dict[str, str] = {}
    properties: dict[str, str] = {}
    for element in root.iter():
        tag = _local(element.tag)
        if tag == "FITSKeyword":
            name = (element.get("name") or "").strip().upper()
            if name in _FITS_TO_XISF and name not in fits_keywords:
                fits_keywords[name] = _card_value(element.get("value") or "")
        elif tag == "Property":
            id_ = element.get("id") or ""
            if id_ in _XISF_PROPERTIES and id_ not in properties:
                value = element.get("value")
                properties[id_] = (value if value is not None else element.text or "").strip()

    # Die XISF-Property hat Vorrang vor dem eingebetteten FITS-Keyword.
    keywords = dict(fits_keywords)
    conflicts = {}
    for keyword, property_id in _FITS_TO_XISF.items():
        if property_id is None or not properties.get(property_id):
            continue
        xisf_value = properties[property_id]
        fits_value = fits_keywords.get(keyword)
        if keyword in _CONFLICT_KEYS and fits_value and not _same(xisf_value, fits_value):
            conflicts[keyword] = fits_value
        keywords[keyword] = xisf_value

    creators = tuple(
        value
        for value in (
            properties.get(_CREATOR_PROPERTY),
            fits_keywords.get("SWCREATE"),
            fits_keywords.get("ORIGIN"),
        )
        if value
    )
    return HeaderValues(keywords=keywords, creators=creators, conflicts=conflicts)


def _same(a: str, b: str) -> bool:
    try:
        return Decimal(a) == Decimal(b)
    except InvalidOperation:
        return a.strip() == b.strip()


# -- Deuten ------------------------------------------------------------------


def seconds(text: str | None) -> Decimal | None:
    """Sekunden > 0 aus einem Header- oder Formularwert, auf die Modellgenauigkeit gerundet."""
    if text is None:
        return None
    try:
        value = Decimal(str(text).strip().replace(",", "."))
    except InvalidOperation:
        return None
    if not value.is_finite():
        return None
    value = value.quantize(SECONDS_PLACES, ROUND_HALF_UP) if value < SECONDS_MAX else None
    return value if value is not None and value > 0 else None


def light_count(text: str | None) -> int | None:
    """Anzahl Lights: eine ganze Zahl ≥ 1, sonst nichts."""
    if text is None:
        return None
    try:
        value = Decimal(str(text).strip())
    except InvalidOperation:
        return None
    if not value.is_finite() or value != value.to_integral_value() or value < 1:
        return None
    return int(value)


# Kanal -> Schreibweisen des Filternamens (normalisiert). Dualband- und Lichtverschmutzungsfilter
# (`HO`, `VIS`, `L-eNhance`, ...) und `IR-cut` stehen bewusst nicht darin: Sie ergeben keinen
# Vorschlag, und `IR-cut` ist das Gegenteil von `IR`.
FILTER_SPELLINGS = {
    "Ha": ("ha", "halpha", "hα", "h"),
    "OIII": ("oiii", "o3", "o"),
    "SII": ("sii", "s2", "s"),
    "L": ("l", "lum", "luminance"),
    "R": ("r", "red"),
    "G": ("g", "green"),
    "B": ("b", "blue"),
    "IR": ("ir", "irpass"),
}
_CHANNEL_BY_SPELLING = {
    spelling: channel for channel, spellings in FILTER_SPELLINGS.items() for spelling in spellings
}
_BANDWIDTH = re.compile(r"\d+(?:[.,]\d+)?\s*nm")
_IGNORED = re.compile(r"[\s\-_.\[\]()]")


def channel_for_filter(text: str | None) -> str | None:
    """Der Kanal zu einem Filternamen aus dem Header, nur bei eindeutigem Treffer.

    Verglichen wird ohne Groß-/Kleinschreibung, ohne Leerzeichen, `-`, `_`, `.`, Klammern und
    ohne Bandbreite (`7nm`). Unbekanntes und Mehrbandfilter ergeben `None`."""
    normalized = _IGNORED.sub("", _BANDWIDTH.sub("", (text or "").casefold()))
    return _CHANNEL_BY_SPELLING.get(normalized)


def meaning_of_exptime(creators) -> tuple[str, Meaning | None]:
    """Erzeuger und die Bedeutung von EXPTIME bei ihm. Gespeichert wird der erste Erzeuger,
    der in der Tabelle steht, sonst der erste überhaupt."""
    for creator in creators:
        for prefix, meaning in EXPTIME_MEANING.items():
            if creator.casefold().startswith(prefix.casefold()):
                return creator, meaning
    return (creators[0] if creators else ""), None


@dataclass(frozen=True)
class FromHeader:
    """Was aus dem Header übernommen wird: direkte Werte mit Herkunft `header`, dazu der
    Erzeuger, ein ungedeutetes EXPTIME (Erzeuger unbekannt) und Widersprüche."""

    values: dict[str, object]
    creator: str
    unknown_exptime: Decimal | None
    conflicts: dict[str, str]
    # Kanal laut Filtername (`channel_for_filter`), sonst leer.
    channel: str = ""


def interpret(header: HeaderValues) -> FromHeader:
    """Deutet die gelesenen Werte. Hier wird nichts gerechnet; das schlägt `proposal` vor."""
    keywords = header.keywords
    values: dict[str, object] = {}
    creator, meaning = meaning_of_exptime(header.creators)

    if (total := seconds(keywords.get("LIVETIME"))) is not None:
        values[TOTAL] = total
    if (count := light_count(keywords.get("STACKCNT"))) is not None:
        values[COUNT] = count
    exptime = seconds(keywords.get("EXPTIME"))
    unknown_exptime = None
    if exptime is not None:
        if meaning is None:
            unknown_exptime = exptime
        else:
            # LIVETIME hat Vorrang: EXPTIME füllt nur, was noch leer ist.
            values.setdefault(meaning.value, exptime)
    for keyword, name in (("INSTRUME", INSTRUMENT), ("TELESCOP", TELESCOPE)):
        if text := (keywords.get(keyword) or "").strip():
            values[name] = text[:TEXT_LENGTH]
    return FromHeader(
        values=values,
        creator=creator[:TEXT_LENGTH],
        unknown_exptime=unknown_exptime,
        conflicts={k: v[:TEXT_LENGTH] for k, v in header.conflicts.items()},
        channel=_channel_from(keywords),
    )


def _channel_from(keywords: dict[str, str]) -> str:
    """Der Kanal zum ersten Filterschlüssel, der gesetzt ist; leer ohne eindeutigen Treffer."""
    name = next((keywords[k] for k in _FILTER_KEYS if keywords.get(k, "").strip()), "")
    return channel_for_filter(name) or ""


def _any_manual(master, names) -> bool:
    return any(getattr(master, f"{name}_source") == Source.MANUAL for name in names)


def apply_header(master, header: HeaderValues, *, keep_manual: bool = False) -> list[str]:
    """Übernimmt die Werte aus dem Header in den Master (ohne zu speichern) und gibt die
    geänderten Modellfelder zurück. Mit `keep_manual` bleiben Werte von Hand unangetastet."""
    found = interpret(header)
    changed = []
    for name, value in found.values.items():
        if keep_manual and getattr(master, f"{name}_source") == Source.MANUAL:
            continue
        setattr(master, name, value)
        setattr(master, f"{name}_source", Source.HEADER)
        changed += [name, f"{name}_source"]
    master.creator = found.creator
    # Hat jemand eine der Zeiten von Hand gesetzt, ist die Frage nach EXPTIME beantwortet.
    if not (keep_manual and _any_manual(master, (PER_LIGHT, TOTAL))):
        master.header_exptime = found.unknown_exptime
    master.header_conflicts = found.conflicts
    # Drei Ebenen (RGB) legen den Kanal fest; nur bei einer Ebene schlägt der Filter einen vor.
    master.header_channel = "" if master.channel == "RGB" else found.channel
    return [*changed, "creator", "header_exptime", "header_conflicts", "header_channel"]


# -- Vorschläge und Hinweise ---------------------------------------------------

_SMOOTH = Decimal("0.01")
MIXED = "Gemischte Belichtungszeiten? Bitte von Hand eintragen."
NO_WHOLE_COUNT = "Daraus ergibt sich keine ganze Anzahl Lights. Bitte von Hand eintragen."

LABELS = {
    PER_LIGHT: "Belichtung pro Light",
    COUNT: "Anzahl Lights",
    TOTAL: "Gesamtbelichtung",
    INSTRUMENT: "Instrument",
    TELESCOPE: "Teleskop",
}


def show(value) -> str:
    """Zahl für die Anzeige: ohne überflüssige Nullen, mit Dezimalkomma."""
    if value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    text = f"{Decimal(value).normalize():f}"
    return text.replace(".", ",")


@dataclass(frozen=True)
class Suggestion:
    """Ein berechneter Wert, den erst ein Klick mit der Herkunft `berechnet` speichert."""

    field: str
    value: Decimal | int
    explanation: str


@dataclass(frozen=True)
class Row:
    name: str
    label: str
    value: object
    source: str

    @property
    def display(self) -> str:
        text = show(self.value) if self.name in NUMBERS else (self.value or "")
        return f"{text} s" if text and self.name in (PER_LIGHT, TOTAL) else text

    @property
    def input(self) -> str:
        return show(self.value) if self.name in NUMBERS else (self.value or "")

    @property
    def source_label(self) -> str:
        return Source(self.source).label if self.source else ""


@dataclass(frozen=True)
class Proposal:
    rows: tuple[Row, ...]
    suggestion: Suggestion | None = None
    hints: tuple[str, ...] = ()
    # Wert von EXPTIME, wenn die Teilnehmenden seine Bedeutung wählen sollen.
    exptime_question: Decimal | None = None
    conflicts: tuple[tuple[str, str], ...] = ()
    # Kanal laut Header, wenn er vom gewählten abweicht (`Master.Channel`-Wert).
    channel_suggestion: str = ""

    @property
    def exptime_question_display(self) -> str:
        return show(self.exptime_question)


def _smooth_per_light(quotient: Decimal) -> Decimal | None:
    """Eine glatte Belichtung pro Light: ab 1 s ganze Sekunden, darunter Zehntelsekunden."""
    step = Decimal(1) if quotient >= 1 else Decimal("0.1")
    target = quotient.quantize(step, ROUND_HALF_UP)
    if target <= 0 or abs(quotient - target) >= _SMOOTH:
        return None
    return target


def _compute(per_light, count, total) -> tuple[Suggestion | None, str | None]:
    """Aus genau zwei der drei Zahlen die dritte; sonst nichts. Gibt (Vorschlag, Hinweis)."""
    if total is not None and count is not None and per_light is None:
        value = _smooth_per_light(total / count)
        if value is None:
            return None, MIXED
        return Suggestion(
            PER_LIGHT, value, f"{show(value)} s, berechnet aus {show(total)} s / {count}."
        ), None
    if per_light is not None and count is not None and total is None:
        value = (per_light * count).quantize(SECONDS_PLACES)
        return Suggestion(
            TOTAL, value, f"{show(value)} s, berechnet aus {show(per_light)} s × {count}."
        ), None
    if per_light is not None and total is not None and count is None:
        quotient = total / per_light
        value = quotient.quantize(Decimal(1), ROUND_HALF_UP)
        if value < 1 or abs(quotient - value) >= _SMOOTH:
            return None, NO_WHOLE_COUNT
        return Suggestion(
            COUNT, int(value), f"{value}, berechnet aus {show(total)} s / {show(per_light)} s."
        ), None
    if None not in (per_light, count, total) and abs(total / count - per_light) >= _SMOOTH:
        return None, (
            f"Die Zahlen passen nicht zusammen: {show(per_light)} s × {count} ergibt nicht "
            f"{show(total)} s."
        )
    return None, None


def _channel_suggestion(master) -> str:
    header = master.header_channel
    return header if header and header != master.channel else ""


def proposal(master) -> Proposal:
    """Was die Submission-Seite zu den Belichtungsangaben zeigt: Werte mit Herkunft, ein Vorschlag
    für einen fehlenden Wert, Hinweise und gegebenenfalls die Frage nach EXPTIME."""
    rows = tuple(
        Row(name, LABELS[name], getattr(master, name), getattr(master, f"{name}_source"))
        for name in FIELDS
    )
    suggestion, hint = _compute(
        master.exposure_per_light, master.light_count, master.total_exposure
    )
    question = master.header_exptime
    if question is not None and question in (master.exposure_per_light, master.total_exposure):
        question = None  # schon gedeutet
    return Proposal(
        rows=rows,
        suggestion=suggestion,
        hints=(hint,) if hint else (),
        exptime_question=question,
        channel_suggestion=_channel_suggestion(master),
        conflicts=tuple(
            (keyword, value)
            for keyword, value in sorted((master.header_conflicts or {}).items())
            if not _any_manual(master, _CONFLICT_FIELDS.get(keyword, ()))
        ),
    )


# -- Ändern durch Teilnehmende oder Betreiber ---------------------------------


class InvalidInput(ValueError):
    """Eine Eingabe zu den Belichtungsangaben ist ungültig."""


def parse(name: str, raw) -> object:
    """Formularwert -> Modellwert; leer heißt „kein Wert“."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return "" if name in (INSTRUMENT, TELESCOPE) else None
    if name == COUNT:
        if isinstance(raw, bool) or (value := light_count(str(raw))) is None:
            raise InvalidInput(f"{LABELS[name]}: bitte eine ganze Zahl ab 1.")
        return value
    if name in (PER_LIGHT, TOTAL):
        if isinstance(raw, bool) or (value := seconds(str(raw))) is None:
            raise InvalidInput(f"{LABELS[name]}: bitte eine Zahl in Sekunden über 0.")
        return value
    if name in (INSTRUMENT, TELESCOPE):
        text = str(raw).strip()
        if len(text) > TEXT_LENGTH:
            raise InvalidInput(f"{LABELS[name]}: höchstens {TEXT_LENGTH} Zeichen.")
        return text
    raise InvalidInput("Unbekanntes Feld.")


def set_by_hand(master, changes: dict) -> list[str]:
    """Übernimmt Werte von Hand (ohne zu speichern). Nur geänderte Werte werden `manuell`;
    ein geleerter Wert verliert seine Herkunft. Gibt die geänderten Modellfelder zurück."""
    parsed = {name: parse(name, raw) for name, raw in changes.items() if name in FIELDS}
    changed = []
    for name, value in parsed.items():
        if value == getattr(master, name):
            continue
        setattr(master, name, value)
        setattr(master, f"{name}_source", Source.MANUAL if value not in (None, "") else "")
        changed += [name, f"{name}_source"]
    return changed + _set_channel(master, changes.get("channel"))


def _set_channel(master, raw) -> list[str]:
    """Kanal von Hand ändern (Herkunft `manuell`). Drei Ebenen (RGB) legen den Kanal fest:
    Zwischen RGB und den Einzelkanälen wechselt niemand, die Prüfung hat sie so zugelassen."""
    if raw is None or raw == master.channel:
        return []
    allowed = {c for c in type(master).Channel.values if c != "RGB"}
    if master.channel == "RGB" or raw not in allowed:
        raise InvalidInput("Kanal: bitte einen der Einzelkanäle wählen.")
    master.channel = raw
    master.channel_source = Source.MANUAL
    return ["channel", "channel_source"]


def accept(master, name: str) -> list[str]:
    """Speichert den aktuellen Vorschlag mit der Herkunft `berechnet` (ohne zu speichern).
    `channel` übernimmt stattdessen den Kanal aus dem Header (Herkunft `header`)."""
    if name == "channel":
        if not (channel := _channel_suggestion(master)):
            raise InvalidInput("Dazu gibt es keinen Vorschlag mehr. Bitte lade die Seite neu.")
        master.channel = channel
        master.channel_source = Source.HEADER
        return ["channel", "channel_source"]
    suggestion = proposal(master).suggestion
    if suggestion is None or suggestion.field != name:
        raise InvalidInput("Dazu gibt es keinen Vorschlag mehr. Bitte lade die Seite neu.")
    setattr(master, name, suggestion.value)
    setattr(master, f"{name}_source", Source.COMPUTED)
    return [name, f"{name}_source"]


def choose_exptime_meaning(master, name: str) -> list[str]:
    """Teilnehmende legen fest, ob EXPTIME die Gesamtzeit oder die Zeit pro Light ist. Der Wert
    stammt aus dem Header; den anderen schlägt `proposal` danach vor."""
    if name not in (TOTAL, PER_LIGHT):
        raise InvalidInput("Bitte wähle Gesamtzeit oder pro Light.")
    if proposal(master).exptime_question is None:
        raise InvalidInput("EXPTIME ist schon gedeutet. Bitte lade die Seite neu.")
    changed = []
    if getattr(master, name) is None:
        setattr(master, name, master.header_exptime)
        setattr(master, f"{name}_source", Source.HEADER)
        changed = [name, f"{name}_source"]
    master.header_exptime = None
    return [*changed, "header_exptime"]


def manifest_values(master) -> dict:
    """Belichtungsangaben eines Masters für Manifest und Export (#34), die aus der Datenbank
    lesen. In der Begleitdatei stehen sie bewusst nicht (ADR 0010)."""
    entry: dict[str, object] = {}
    for name in FIELDS:
        value = getattr(master, name)
        if isinstance(value, Decimal):
            value = f"{value.normalize():f}"
        entry[name] = {
            "value": value if value != "" else None,
            "source": getattr(master, f"{name}_source"),
        }
    entry["creator"] = master.creator
    entry["channel_source"] = master.channel_source
    return entry
