import uuid
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

GIB = 1024**3


def default_quota() -> int:
    return settings.DEFAULT_QUOTA_BYTES


def default_cap() -> int:
    return settings.DEFAULT_GLOBAL_CAP_BYTES


class Event(models.Model):
    """Eine Aktion, z. B. ein Projekt. Teilnehmende kommen über die Projektwebsite."""

    slug = models.SlugField(unique=True)
    title = models.CharField("Titel", max_length=200)
    description = models.TextField("Beschreibung", blank=True)
    opens_at = models.DateTimeField("Beginn", null=True, blank=True)
    closes_at = models.DateTimeField("Ende", null=True, blank=True)
    active = models.BooleanField("Aktiv", default=True)
    entry_origins = models.JSONField(
        "Erlaubte Herkunfts-Origins",
        default=list,
        blank=True,
        help_text='Liste, z. B. ["https://projekt.example.org"]. Nur https.',
    )
    entry_page_url = models.URLField("Link zurück zur Projektseite", blank=True)
    quota_bytes_per_submission = models.PositiveBigIntegerField(
        "Quote je Abgabe (Bytes)", default=default_quota
    )
    global_cap_bytes = models.PositiveBigIntegerField("Gesamtgrenze (Bytes)", default=default_cap)
    max_file_bytes = models.PositiveBigIntegerField("Max. Dateigröße (Bytes)", default=2 * GIB)
    use_fpack = models.BooleanField("fpack für Integer-FITS", default=False)
    delete_originals_after_pack = models.BooleanField(
        "Originale nach dem Packen löschen", default=False
    )
    auto_close_after_idle_minutes = models.PositiveIntegerField(
        "Stack automatisch schließen nach (Minuten Leerlauf)", default=120
    )
    altcha_enabled = models.BooleanField(
        "ALTCHA im Teilnahmeformular",
        default=False,
        help_text="Nur einschalten, wenn Missbrauch auftritt.",
    )

    class Meta:
        verbose_name = "Event"
        verbose_name_plural = "Events"

    def __str__(self) -> str:
        return self.title

    def clean(self):
        origins = self.entry_origins
        if not isinstance(origins, list) or not all(isinstance(o, str) for o in origins):
            raise ValidationError({"entry_origins": "Muss eine Liste von Texten sein."})
        for origin in origins:
            parsed = urlparse(origin)
            if (
                parsed.scheme != "https"
                or not parsed.netloc
                or parsed.path not in ("", "/")
                or parsed.params
                or parsed.query
                or parsed.fragment
            ):
                raise ValidationError(
                    {"entry_origins": f"{origin!r} ist kein https-Origin (https://host[:port])."}
                )
        if self.opens_at and self.closes_at and self.closes_at <= self.opens_at:
            raise ValidationError({"closes_at": "Das Ende muss nach dem Beginn liegen."})

    def is_open(self, now=None) -> bool:
        now = now or timezone.now()
        if not self.active:
            return False
        if self.opens_at and now < self.opens_at:
            return False
        return not (self.closes_at and now >= self.closes_at)


class Submission(models.Model):
    """Eine Abgabe einer Person. Zugang über einen persönlichen Link, nur als Hash gespeichert."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="submissions")
    display_name = models.CharField("Anzeigename / Credit", max_length=80)
    email = models.EmailField("E-Mail", blank=True)
    region = models.CharField("Region", max_length=80, blank=True)
    bortle = models.PositiveSmallIntegerField(
        "Bortle-Klasse",
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(9)],
    )
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(null=True, blank=True, editable=False)
    ip_hash = models.CharField(max_length=64, blank=True, editable=False)
    equipment_photo_key = models.CharField(max_length=300, blank=True)
    is_blocked = models.BooleanField("Gesperrt", default=False)

    class Meta:
        verbose_name = "Abgabe"
        verbose_name_plural = "Abgaben"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.display_name

    def clean(self):
        if len(self.display_name.strip()) < 2:
            raise ValidationError({"display_name": "Mindestens 2 Zeichen."})


def detect_platform(url: str) -> str:
    """Erkennt die Plattform eines Links anhand des Hostnamens (nur Anzeige, keine Prüfung)."""
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    known = {
        "instagram.com": "Instagram",
        "astrobin.com": "AstroBin",
        "youtube.com": "YouTube",
        "youtu.be": "YouTube",
        "flickr.com": "Flickr",
        "facebook.com": "Facebook",
        "x.com": "X",
        "twitter.com": "X",
        "bsky.app": "Bluesky",
        "github.com": "GitHub",
        "reddit.com": "Reddit",
        "500px.com": "500px",
    }
    for domain, name in known.items():
        if host == domain or host.endswith("." + domain):
            return name
    return "Webseite"


MAX_SOCIAL_LINKS = 4


class SocialLink(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="links")
    url = models.URLField("Link", max_length=300)
    platform = models.CharField("Plattform", max_length=40, blank=True, editable=False)

    class Meta:
        verbose_name = "Link"
        verbose_name_plural = "Links"

    def __str__(self) -> str:
        return self.url

    def save(self, *args, **kwargs):
        self.platform = detect_platform(self.url)
        super().save(*args, **kwargs)

    def clean(self):
        if urlparse(self.url).scheme != "https":
            raise ValidationError({"url": "Nur https-Links sind erlaubt."})
        if self.submission_id:
            others = SocialLink.objects.filter(submission_id=self.submission_id).exclude(pk=self.pk)
            if others.count() >= MAX_SOCIAL_LINKS:
                raise ValidationError(f"Höchstens {MAX_SOCIAL_LINKS} Links je Abgabe.")


class Consent(models.Model):
    PRIVACY_READ = "privacy_read"
    PROJECT_USE = "project_use"
    PUBLISH_NAME_LINKS = "publish_name_links"
    PUBLISH_EQUIPMENT_PHOTO = "publish_equipment_photo"
    STATUS_MAILS = "status_mails"
    KINDS = [
        (PRIVACY_READ, "Datenschutzhinweise gelesen"),
        (PROJECT_USE, "Nutzung im Projekt"),
        (PUBLISH_NAME_LINKS, "Name und Links veröffentlichen"),
        (PUBLISH_EQUIPMENT_PHOTO, "Equipment-Foto veröffentlichen"),
        (STATUS_MAILS, "Status-Mails"),
    ]

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="consents")
    kind = models.CharField(max_length=40, choices=KINDS)
    granted = models.BooleanField(default=False)
    granted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    text_version = models.CharField("Version des Einwilligungstexts", max_length=40, blank=True)

    class Meta:
        verbose_name = "Einwilligung"
        verbose_name_plural = "Einwilligungen"
        constraints = [
            models.UniqueConstraint(fields=["submission", "kind"], name="uniq_consent_kind")
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()}: {'ja' if self.granted else 'nein'}"

    def grant(self, text_version: str = ""):
        self.granted = True
        self.granted_at = timezone.now()
        self.revoked_at = None
        self.text_version = text_version
        self.save()

    def revoke(self):
        self.granted = False
        self.revoked_at = timezone.now()
        self.save()


class Stack(models.Model):
    OPEN, CLOSED, QUEUED, PACKING, DONE, FAILED = (
        "open",
        "closed",
        "queued",
        "packing",
        "done",
        "failed",
    )
    STATES = [
        (OPEN, "Offen"),
        (CLOSED, "Abgeschlossen"),
        (QUEUED, "Wartet auf Verarbeitung"),
        (PACKING, "Wird gepackt"),
        (DONE, "Fertig"),
        (FAILED, "Fehler"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="stacks")
    object_name = models.CharField("Objekt / Titel", max_length=200)
    capture_dates = models.CharField("Aufnahmedatum(e)", max_length=200, blank=True)
    description = models.TextField("Beschreibung", blank=True)
    telescope = models.CharField("Teleskop / Objektiv", max_length=200)
    focal_length_mm = models.PositiveIntegerField("Brennweite (mm)", null=True, blank=True)
    aperture_mm = models.PositiveIntegerField("Öffnung (mm)", null=True, blank=True)
    focal_ratio = models.DecimalField(
        "Öffnungsverhältnis f/", max_digits=5, decimal_places=2, null=True, blank=True
    )
    reducer_barlow = models.CharField("Reducer / Barlow", max_length=100, blank=True)
    camera = models.CharField("Kamera", max_length=200)
    mount = models.CharField("Montierung", max_length=200, blank=True)
    filters = models.CharField("Filter", max_length=200, blank=True)
    has_darks = models.BooleanField("Darks", default=False)
    has_flats = models.BooleanField("Flats", default=False)
    has_bias = models.BooleanField("Bias", default=False)
    has_darkflats = models.BooleanField("Dark-Flats", default=False)
    notes = models.TextField("Hinweise", blank=True)
    state = models.CharField(max_length=10, choices=STATES, default=OPEN, db_index=True)
    last_upload_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    packed_key = models.CharField(max_length=300, blank=True)
    packed_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    original_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    sha256_archive = models.CharField(max_length=64, blank=True)
    error_message = models.TextField(blank=True)
    header_summary = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        verbose_name = "Stack"
        verbose_name_plural = "Stacks"

    def __str__(self) -> str:
        return f"{self.object_name} ({self.submission})"

    def save(self, *args, **kwargs):
        # f/ wird aus Brennweite und Öffnung berechnet, wenn es nicht von Hand gesetzt ist
        if self.focal_ratio is None and self.focal_length_mm and self.aperture_mm:
            self.focal_ratio = round(self.focal_length_mm / self.aperture_mm, 2)
        super().save(*args, **kwargs)

    CHIPS = {
        OPEN: "Offen – Dateien hinzufügen",
        CLOSED: "Hochgeladen",
        QUEUED: "Wartet auf Verarbeitung",
        PACKING: "Wird gepackt",
        DONE: "Fertig ✓",
        FAILED: "Fehler – wir kümmern uns",
    }

    @property
    def chip(self) -> str:
        """Kurzer Status für die Teilnehmenden."""
        return self.CHIPS[self.state]

    @property
    def total_exposure_seconds(self) -> float:
        return sum(line.count * line.seconds for line in self.exposure_lines.all())


class ExposureLine(models.Model):
    stack = models.ForeignKey(Stack, on_delete=models.CASCADE, related_name="exposure_lines")
    filter = models.CharField("Filter", max_length=60, blank=True)
    count = models.PositiveIntegerField("Anzahl", validators=[MinValueValidator(1)])
    seconds = models.FloatField("Sekunden je Bild", validators=[MinValueValidator(0.001)])
    gain_iso = models.CharField("Gain / ISO", max_length=20, blank=True)
    sensor_temp_c = models.FloatField("Sensortemperatur (°C)", null=True, blank=True)

    class Meta:
        verbose_name = "Belichtung"
        verbose_name_plural = "Belichtungen"

    def __str__(self) -> str:
        return f"{self.count} × {self.seconds:g} s {self.filter}".strip()
