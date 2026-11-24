import enum
import uuid
from datetime import datetime, timedelta

from django.db import models
from django.utils import timezone

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


class Campaign(models.Model):
    """Die Aktion: genau ein Datensatz je Installation (ADR 0004)."""

    singleton = models.BooleanField(default=True, unique=True, editable=False)
    object_name = models.CharField("Objekt", max_length=200)
    starts_at = models.DateTimeField("Beginn")
    ends_at = models.DateTimeField("Ende der Aktion")
    grace_period = models.DurationField("Nachfrist", default=timedelta(hours=6))
    quota = models.PositiveBigIntegerField("Quote je Abgabe (Bytes)")
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

    @property
    def closes_at(self) -> datetime:
        """Ende der Aktion plus Nachfrist: ab hier ist jede Abgabe schreibgeschützt."""
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
    """Abgabe: Beitrag einer teilnehmenden Person mit einem Setup."""

    class WithdrawnBy(models.TextChoices):
        PARTICIPANT = "participant", "Teilnehmende"
        OPERATOR = "operator", "Betreiber"

    reference = models.CharField("Abgabe-Kennung", max_length=16, unique=True)
    # Nennung: nur mit gültiger Einwilligung zur Veröffentlichung, sonst leer (anonym).
    credit_name = models.CharField("Nennung", max_length=120, blank=True)
    setup_description = models.TextField("Setup", blank=True, max_length=2000)
    created_at = models.DateTimeField("angelegt", auto_now_add=True)
    # Rückzug: Nach ihm bleiben nur Kennung, Zeitpunkt und wer ihn ausgelöst hat.
    withdrawn_at = models.DateTimeField("zurückgezogen am", null=True, blank=True)
    withdrawn_by = models.CharField(
        "zurückgezogen durch", max_length=16, choices=WithdrawnBy.choices, blank=True
    )

    class Meta:
        verbose_name = "Abgabe"
        verbose_name_plural = "Abgaben"
        ordering = ["created_at"]

    def __str__(self):
        return self.reference

    @property
    def is_withdrawn(self) -> bool:
        return self.withdrawn_at is not None

    @property
    def publishes_credit(self) -> bool:
        """Ob eine gültige (nicht widerrufene) Einwilligung zur Veröffentlichung vorliegt."""
        return self.consents.filter(
            kind=Consent.Kind.PUBLISH_CREDIT, revoked_at__isnull=True
        ).exists()


class Consent(models.Model):
    """Einwilligung: eine einzelne, ausdrücklich erteilte Zustimmung."""

    class Kind(models.TextChoices):
        PROJECT_USE = "project_use", "Nutzung im Projekt"
        PUBLISH_CREDIT = "publish_credit", "Veröffentlichung der Nennung"

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
            models.UniqueConstraint(fields=["submission", "kind"], name="consent_once_per_kind")
        ]

    def __str__(self):
        return f"{self.submission} – {self.get_kind_display()}"


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
    completed_at = models.DateTimeField("abgeschlossen", null=True, blank=True)

    class Meta:
        verbose_name = "Master"
        verbose_name_plural = "Master"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.submission} {self.channel} {self.original_name}"

    @property
    def sidecar_key(self) -> str:
        return self.key.rsplit(".", 1)[0] + ".json"
