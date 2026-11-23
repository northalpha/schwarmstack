from django.contrib.admin.models import LogEntry
from django.db import models


class ProtocolEntry(LogEntry):
    """Protokoll: Djangos LogEntry, im Admin unter dem Namen, den die Betreiber benutzen."""

    class Meta:
        proxy = True
        verbose_name = "Protokolleintrag"
        verbose_name_plural = "Protokoll"


class LoginAttempt(models.Model):
    """Fehlgeschlagene Anmeldung am Admin. Die IP steht nur als Hash darin (ADR 0002).

    Gezählt wird in der Datenbank, nicht im Cache: gunicorn läuft mit mehreren Prozessen.
    """

    ip_hash = models.CharField(max_length=64, db_index=True)
    at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "fehlgeschlagene Anmeldung"
        verbose_name_plural = "fehlgeschlagene Anmeldungen"

    def __str__(self):
        return f"{self.ip_hash[:8]} {self.at:%Y-%m-%d %H:%M}"
