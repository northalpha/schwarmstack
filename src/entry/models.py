from django.db import models

from submissions.models import Event


class EntryAttempt(models.Model):
    """Ein Aufruf von /start/<slug>/. Der Referer wird nur geprüft, nie gespeichert.

    Dient dem Rate-Limit (je gehashter IP) und der Statistik: abgelehnte Versuche sind ein
    Hinweis auf Missbrauch.
    """

    event = models.ForeignKey(Event, null=True, blank=True, on_delete=models.SET_NULL)
    accepted = models.BooleanField()
    ip_hash = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Einstiegsversuch"
        verbose_name_plural = "Einstiegsversuche"

    def __str__(self) -> str:
        return f"{'ok' if self.accepted else 'abgelehnt'} {self.created_at:%d.%m. %H:%M}"
