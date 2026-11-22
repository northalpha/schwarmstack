from django.db import models


class UsedChallenge(models.Model):
    """Gelöste ALTCHA-Aufgaben: jede gilt nur einmal (Schutz gegen Wiederverwendung der Lösung)."""

    signature = models.CharField(max_length=128, unique=True)
    used_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self) -> str:
        return self.signature[:12]
