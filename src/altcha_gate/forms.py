from django import forms

from . import services


class AltchaFormMixin:
    """Formular-Baustein: verlangt eine gültige ALTCHA-Lösung, wenn das Event es eingeschaltet hat.

    Verwendung: `class MeinForm(AltchaFormMixin, forms.Form)` und im Aufruf
    `MeinForm(data, altcha_enabled=event.altcha_enabled)`. Das Widget (Template
    altcha_gate/widget.html) schickt die Lösung im Feld "altcha".
    """

    def __init__(self, *args, altcha_enabled: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.altcha_enabled = altcha_enabled
        if altcha_enabled:
            self.fields["altcha"] = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean(self):
        cleaned = super().clean()
        if self.altcha_enabled and not services.verify_payload(self.data.get("altcha")):
            raise forms.ValidationError(
                "Die Sicherheitsprüfung ist fehlgeschlagen. Bitte versuche es noch einmal."
            )
        return cleaned
