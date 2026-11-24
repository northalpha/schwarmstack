from django import forms

REQUIRED = "Pflichtangabe: Bitte ausfüllen."


class SubmissionForm(forms.Form):
    credit_name = forms.CharField(
        label="Nennung",
        max_length=120,
        required=False,
        help_text=(
            "Unter diesem Namen wirst du im Projekt genannt. Nur mit Häkchen bei der "
            "Veröffentlichung; ohne Häkchen speichern wir keinen Namen."
        ),
    )
    setup_description = forms.CharField(
        label="Dein Setup",
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Zum Beispiel Teleskop und Kamera. Freiwillig.",
    )
    consent_project_use = forms.BooleanField(
        label="Ich bin einverstanden, dass meine Master im Projekt verwendet werden.",
        error_messages={"required": "Pflichtangabe: Ohne diese Einwilligung geht es nicht."},
    )
    consent_publish_credit = forms.BooleanField(
        label="Meine Nennung darf veröffentlicht werden.",
        required=False,
        help_text="Freiwillig. Ohne Häkchen trägst du anonym bei.",
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("consent_publish_credit") and not cleaned.get("credit_name"):
            self.add_error(
                "credit_name",
                "Pflichtangabe: Ohne Nennung können wir dich nicht nennen. Trag einen Namen ein "
                "oder nimm das Häkchen bei der Veröffentlichung weg.",
            )
        return cleaned
