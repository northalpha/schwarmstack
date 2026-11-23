import enum
import uuid
from datetime import datetime, timedelta

from django.db import models
from django.utils import timezone


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

    reference = models.CharField("Abgabe-Kennung", max_length=16, unique=True)
    credit_name = models.CharField("Nennung", max_length=120)
    setup_description = models.TextField("Setup", blank=True, max_length=2000)
    created_at = models.DateTimeField("angelegt", auto_now_add=True)

    class Meta:
        verbose_name = "Abgabe"
        verbose_name_plural = "Abgaben"
        ordering = ["created_at"]

    def __str__(self):
        return self.reference


class Consent(models.Model):
    """Einwilligung: eine einzelne, ausdrücklich erteilte Zustimmung."""

    class Kind(models.TextChoices):
        PROJECT_USE = "project_use", "Nutzung im Projekt"
        PUBLISH_CREDIT = "publish_credit", "Veröffentlichung der Nennung"

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="consents")
    kind = models.CharField(max_length=32, choices=Kind.choices)
    granted_at = models.DateTimeField(auto_now_add=True)
    text_version = models.CharField(max_length=32)

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

    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="masters")
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    channel = models.CharField("Kanal", max_length=8, choices=Channel.choices)
    original_name = models.CharField("Dateiname", max_length=255)
    declared_size = models.PositiveBigIntegerField("angemeldete Größe")
    size = models.PositiveBigIntegerField("Größe", null=True, blank=True)
    key = models.CharField("Objekt-Schlüssel", max_length=255, unique=True)
    upload_id = models.CharField(max_length=1024, blank=True)
    state = models.CharField(max_length=16, choices=State.choices, default=State.UPLOADING)
    rejection_reason = models.CharField("Grund der Ablehnung", max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Master"
        verbose_name_plural = "Master"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.submission} {self.channel} {self.original_name}"

    @property
    def sidecar_key(self) -> str:
        return self.key.rsplit(".", 1)[0] + ".json"
