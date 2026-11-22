import uuid

from django.db import models

from submissions.models import Stack


class UploadedFile(models.Model):
    STARTED, FINISHED, VALIDATING, VALID, REJECTED, ABORTED, DELETED = (
        "started",
        "finished",
        "validating",
        "valid",
        "rejected",
        "aborted",
        "deleted",
    )
    STATES = [
        (STARTED, "Lädt hoch"),
        (FINISHED, "Hochgeladen"),
        (VALIDATING, "Wird geprüft"),
        (VALID, "Gültig"),
        (REJECTED, "Abgelehnt"),
        (ABORTED, "Abgebrochen"),
        (DELETED, "Gelöscht"),
    ]
    # Diese Zustände zählen auf die Quote; abgelehnte, abgebrochene und
    # gelöschte Dateien geben sie frei.
    COUNTED_STATES = (STARTED, FINISHED, VALIDATING, VALID)

    FORMATS = [("fits", "FITS"), ("xisf", "XISF")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stack = models.ForeignKey(Stack, on_delete=models.CASCADE, related_name="files")
    tus_id = models.CharField(max_length=200, blank=True, db_index=True)
    s3_bucket = models.CharField(max_length=100, blank=True)
    s3_key = models.CharField(max_length=300, blank=True)
    filename = models.CharField(max_length=255)
    size_bytes = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    format = models.CharField(max_length=4, choices=FORMATS)
    state = models.CharField(max_length=10, choices=STATES, default=STARTED, db_index=True)
    reject_reason = models.CharField(max_length=200, blank=True)
    header = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Datei"
        verbose_name_plural = "Dateien"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return self.filename
