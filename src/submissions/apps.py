from django.apps import AppConfig


class SubmissionsConfig(AppConfig):
    name = "submissions"
    verbose_name = "Abgaben"

    def ready(self):
        from . import privacy  # noqa: F401  (registriert die Prüfung des Datenschutzhinweises)
