from django.db import models

from submissions.models import Stack
from uploads.models import UploadedFile


class PackJob(models.Model):
    """Eintrag der DB-Warteschlange (kein Celery/Redis).

    Abweichung vom Plan ("stack 1:1"): Prüfaufträge gelten je Datei, Packaufträge je Stack.
    Darum: uploaded_file nur bei kind=validate, höchstens ein Auftrag je Datei
    bzw. je Stack und Art.
    """

    VALIDATE, PACK = "validate", "pack"
    KINDS = [(VALIDATE, "Prüfen"), (PACK, "Packen")]
    QUEUED, RUNNING, DONE, FAILED = "queued", "running", "done", "failed"
    STATES = [
        (QUEUED, "Wartet"),
        (RUNNING, "Läuft"),
        (DONE, "Fertig"),
        (FAILED, "Fehler"),
    ]

    stack = models.ForeignKey(Stack, on_delete=models.CASCADE, related_name="jobs")
    uploaded_file = models.ForeignKey(
        UploadedFile, null=True, blank=True, on_delete=models.CASCADE, related_name="jobs"
    )
    kind = models.CharField(max_length=10, choices=KINDS)
    state = models.CharField(max_length=10, choices=STATES, default=QUEUED, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.CharField(max_length=100, blank=True)
    log = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Auftrag"
        verbose_name_plural = "Aufträge"
        constraints = [
            models.UniqueConstraint(
                fields=["stack", "kind"],
                condition=models.Q(kind="pack"),
                name="uniq_pack_job_per_stack",
            ),
            models.UniqueConstraint(
                fields=["uploaded_file"],
                condition=models.Q(kind="validate"),
                name="uniq_validate_job_per_file",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} {self.stack_id} ({self.get_state_display()})"
