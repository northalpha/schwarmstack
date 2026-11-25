import enum
import uuid
from datetime import datetime, timedelta

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property

from . import exposure
from .exposure import Source
from .validation import Category


class Phase(enum.Enum):
    """Zeitfenster der Aktion. Die einzige Stelle, an der Zeiten verglichen werden."""

    BEFORE = "vor Beginn"
    OPEN = "laufend"
    GRACE = "in der Nachfrist"
    CLOSED = "schreibgeschützt"

    @property
    def accepts_new_submissions(self) -> bool:
        return self is Phase.OPEN

    @property
    def allows_changes_by_participants(self) -> bool:
        """Master löschen und Löschung durch Teilnehmende nur bis zum Ende der Aktion (ADR 0002).

        In der Nachfrist dürfen nur begonnene Uploads noch abschließen.
        """
        return self is Phase.OPEN


class Campaign(models.Model):
    """Die Aktion: genau ein Datensatz je Installation (ADR 0004)."""

    singleton = models.BooleanField(default=True, unique=True, editable=False)
    object_name = models.CharField("Objekt", max_length=200)
    starts_at = models.DateTimeField("Beginn")
    ends_at = models.DateTimeField("Ende der Aktion")
    grace_period = models.DurationField("Nachfrist", default=timedelta(hours=6))
    quota = models.PositiveBigIntegerField("Quote je Submission (Bytes)")
    global_cap = models.PositiveBigIntegerField("Gesamtgrenze (Bytes)")
    max_master_size = models.PositiveBigIntegerField(
        "Höchstgröße je Master (Bytes)", default=500 * 1024**2
    )

    class Meta:
        verbose_name = "Aktion"
        verbose_name_plural = "Aktion"
        constraints = [
            models.CheckConstraint(condition=models.Q(singleton=True), name="campaign_singleton")
        ]

    def __str__(self):
        return self.object_name

    @classmethod
    def current(cls) -> "Campaign | None":
        return cls.objects.first()

    @classmethod
    def current_phase(cls) -> Phase:
        """Phase der Aktion jetzt; ohne eingerichtete Aktion ist alles geschlossen."""
        campaign = cls.current()
        return campaign.phase() if campaign else Phase.CLOSED

    def clean(self):
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "Das Ende der Aktion muss nach dem Beginn liegen."})

    @property
    def closes_at(self) -> datetime:
        """Ende der Aktion plus Nachfrist: ab hier ist jede Submission schreibgeschützt."""
        return self.ends_at + self.grace_period

    def phase(self, now: datetime | None = None) -> Phase:
        now = now or timezone.now()
        if now < self.starts_at:
            return Phase.BEFORE
        if now < self.ends_at:
            return Phase.OPEN
        if now < self.closes_at:
            return Phase.GRACE
        return Phase.CLOSED


class Submission(models.Model):
    """Submission: was eine teilnehmende Person mit einem Setup zur Aktion beiträgt."""

    class DeletedBy(models.TextChoices):
        PARTICIPANT = "participant", "Teilnehmende"
        OPERATOR = "operator", "Betreiber"

    reference = models.CharField("Submission-ID", max_length=16, unique=True)
    # Namensnennung: nur mit gültiger Einwilligung zur Namensnennung, sonst leer (anonym).
    credit_name = models.CharField("Namensnennung", max_length=120, blank=True)
    setup_description = models.TextField("Setup", blank=True, max_length=2000)
    created_at = models.DateTimeField("angelegt", auto_now_add=True)
    # Löschung: Danach bleiben nur Submission-ID, Zeitpunkt und wer gelöscht hat.
    deleted_at = models.DateTimeField("gelöscht am", null=True, blank=True)
    deleted_by = models.CharField(
        "gelöscht durch", max_length=16, choices=DeletedBy.choices, blank=True
    )

    class Meta:
        verbose_name = "Submission"
        verbose_name_plural = "Submissions"
        ordering = ["created_at"]

    def __str__(self):
        return self.reference

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @property
    def deleted_by_participant(self) -> bool:
        return self.deleted_by == self.DeletedBy.PARTICIPANT

    def clean(self):
        # Mit gültiger Einwilligung zur Namensnennung gehört ein Name dazu (Ticket #33).
        if self.pk and not self.credit_name.strip() and self.publishes_credit:
            raise ValidationError(
                {
                    "credit_name": "Mit Einwilligung zur Namensnennung braucht die Submission "
                    "eine Namensnennung. Soll sie anonym werden, den Widerruf der "
                    "Namensnennung vermerken."
                }
            )

    @property
    def photo(self) -> "EquipmentPhoto | None":
        """Das Equipment-Foto dieser Submission, wenn sie eines hat."""
        try:
            return self.equipment_photo
        except ObjectDoesNotExist:
            return None

    @property
    def publishes_credit(self) -> bool:
        """Ob eine gültige (nicht widerrufene) Einwilligung zur Namensnennung vorliegt."""
        return self.consents.filter(
            kind=Consent.Kind.PUBLISH_CREDIT, revoked_at__isnull=True
        ).exists()


class Consent(models.Model):
    """Einwilligung: ausdrücklich von den Teilnehmenden erteilt, je Zweck eine eigene."""

    class Kind(models.TextChoices):
        PROJECT_USE = "project_use", "Nutzung im Projekt"
        PUBLISH_CREDIT = "publish_credit", "Namensnennung"
        EQUIPMENT_PHOTO = "equipment_photo", "Equipment-Foto"

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="consents")
    kind = models.CharField("Art", max_length=32, choices=Kind.choices)
    granted_at = models.DateTimeField("erteilt am", auto_now_add=True)
    text_version = models.CharField("Fassung des Hinweistextes", max_length=32)
    # Widerruf: Die Einwilligung bleibt stehen, damit nachweisbar ist, was wann galt.
    revoked_at = models.DateTimeField("widerrufen am", null=True, blank=True)

    class Meta:
        verbose_name = "Einwilligung"
        verbose_name_plural = "Einwilligungen"
        constraints = [
            # Je Zweck gilt höchstens eine nicht widerrufene Einwilligung; eine widerrufene bleibt
            # als Nachweis stehen, und wer erneut einwilligt, bekommt eine neue.
            models.UniqueConstraint(
                fields=["submission", "kind"],
                condition=models.Q(revoked_at__isnull=True),
                name="consent_once_per_kind",
            )
        ]

    def __str__(self):
        return f"{self.submission} – {self.get_kind_display()}"


class EquipmentPhoto(models.Model):
    """Equipment-Foto: höchstens eines je Submission, bereinigt und mit Thumbnail (Ticket #82).

    Die Objekt-Schlüssel entstehen aus Submission-ID und einer Zufalls-ID, nie aus dem
    Dateinamen der Teilnehmenden, der nirgends gespeichert wird.
    """

    submission = models.OneToOneField(
        Submission, on_delete=models.CASCADE, related_name="equipment_photo"
    )
    key = models.CharField("Objekt-Schlüssel", max_length=255, unique=True)
    thumbnail_key = models.CharField("Objekt-Schlüssel des Thumbnails", max_length=255, unique=True)
    saved_at = models.DateTimeField("gespeichert am", default=timezone.now)

    class Meta:
        verbose_name = "Equipment-Foto"
        verbose_name_plural = "Equipment-Fotos"

    def __str__(self):
        return f"{self.submission} – Equipment-Foto"


def _source_field():
    return models.CharField("Herkunft", max_length=16, choices=Source.choices, blank=True)


class Master(models.Model):
    """Master: eine hochgeladene integrierte Bilddatei für genau einen Kanal."""

    class Channel(models.TextChoices):
        L = "L", "L"
        R = "R", "R"
        G = "G", "G"
        B = "B", "B"
        HA = "Ha", "Hα"
        OIII = "OIII", "OIII"
        SII = "SII", "SII"
        IR = "IR", "IR"
        RGB = "RGB", "RGB"

    class State(models.TextChoices):
        UPLOADING = "uploading", "im Upload"
        ACCEPTED = "accepted", "angenommen"
        REJECTED = "rejected", "abgelehnt"
        ABORTED = "aborted", "abgebrochen"

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="masters")
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    channel = models.CharField("Kanal", max_length=8, choices=Channel.choices)
    original_name = models.CharField("Dateiname", max_length=255)
    declared_size = models.PositiveBigIntegerField("angemeldete Größe")
    size = models.PositiveBigIntegerField("Größe", null=True, blank=True)
    key = models.CharField("Objekt-Schlüssel", max_length=255, unique=True)
    upload_id = models.CharField(max_length=1024, blank=True)
    state = models.CharField(
        "Zustand", max_length=16, choices=State.choices, default=State.UPLOADING
    )
    rejection_reason = models.CharField("Grund der Ablehnung", max_length=255, blank=True)
    rejection_category = models.CharField(
        "Art der Ablehnung",
        max_length=16,
        blank=True,
        choices=[(c.value, c.label) for c in Category],
    )
    # Vom Browser berechnet und gemeldet, vom Server nicht bestätigt (ADR 0005).
    sha256 = models.CharField("Prüfsumme", max_length=64, blank=True, db_index=True)
    duplicate_of = models.ForeignKey(
        "self",
        verbose_name="Dublette von",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="duplicates",
    )
    created_at = models.DateTimeField("angelegt", auto_now_add=True)
    # Letzte Anfrage des Browsers zu diesem Upload (Start oder Signieren).
    last_activity_at = models.DateTimeField("zuletzt aktiv", null=True, blank=True)
    completed_at = models.DateTimeField("abgeschlossen", null=True, blank=True)

    # Belichtungsangaben (ADR 0010): je Wert eine Herkunft, leer heißt „kein Wert“.
    exposure_per_light = models.DecimalField(
        "Belichtung pro Light (s)", max_digits=14, decimal_places=4, null=True, blank=True
    )
    exposure_per_light_source = _source_field()
    light_count = models.PositiveIntegerField("Anzahl Lights", null=True, blank=True)
    light_count_source = _source_field()
    total_exposure = models.DecimalField(
        "Gesamtbelichtung (s)", max_digits=14, decimal_places=4, null=True, blank=True
    )
    total_exposure_source = _source_field()
    instrument = models.CharField("Instrument", max_length=100, blank=True)
    instrument_source = _source_field()
    telescope = models.CharField("Teleskop", max_length=100, blank=True)
    telescope_source = _source_field()
    creator = models.CharField("Erzeuger", max_length=100, blank=True)
    # EXPTIME eines unbekannten Erzeugers: Was es bedeutet, entscheiden die Teilnehmenden.
    header_exptime = models.DecimalField(
        "EXPTIME ungedeutet (s)", max_digits=14, decimal_places=4, null=True, blank=True
    )
    # FITS-Keyword -> sein Wert, wenn die XISF-Property ihm widersprach und Vorrang hatte.
    header_conflicts = models.JSONField("Widersprüche im Header", default=dict, blank=True)

    class Meta:
        verbose_name = "Master"
        verbose_name_plural = "Master"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.submission} {self.channel} {self.original_name}"

    @cached_property
    def exposure_proposal(self) -> exposure.Proposal:
        """Belichtungsangaben für die Anzeige: Werte, Vorschlag, Hinweise."""
        return exposure.proposal(self)

    @property
    def sidecar_key(self) -> str:
        return self.key.rsplit(".", 1)[0] + ".json"
