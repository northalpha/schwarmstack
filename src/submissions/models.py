from datetime import timedelta

from django.db import models


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
