from django import forms


class SubmissionForm(forms.Form):
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
        label="Mein Name darf im Projekt genannt werden (Namensnennung).",
        required=False,
        help_text="Freiwillig. Ohne Häkchen trägst du anonym bei.",
    )
    # Nach dem Häkchen, an dem sie hängt (Ticket #33); namensnennung.js koppelt beides im Browser.
    credit_name = forms.CharField(
        label="Namensnennung",
        max_length=120,
        required=False,
        help_text=(
            "Unter diesem Namen wirst du im Projekt genannt. Nur mit Häkchen bei der "
            "Namensnennung; ohne Häkchen speichern wir keinen Namen."
        ),
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("consent_publish_credit") and not cleaned.get("credit_name"):
            self.add_error(
                "credit_name",
                "Pflichtangabe: Ohne Namen können wir dich nicht nennen. Trag einen Namen ein "
                "oder nimm das Häkchen bei der Namensnennung weg.",
            )
        return cleaned


class DetailsForm(forms.Form):
    """Angaben ändern: Setup und Namensnennung. Die Namensnennung gibt es nur mit gültiger
    Einwilligung zur Namensnennung und ist dann Pflicht (wie `Submission.clean`)."""

    setup_description = forms.CharField(
        label="Dein Setup",
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Zum Beispiel Teleskop und Kamera. Freiwillig.",
    )
    credit_name = forms.CharField(
        label="Namensnennung",
        max_length=120,
        help_text="Unter diesem Namen wirst du im Projekt genannt.",
        error_messages={
            "required": "Pflichtangabe: Mit Einwilligung zur Namensnennung braucht die "
            "Submission einen Namen."
        },
    )

    def __init__(self, *args, submission, **kwargs):
        super().__init__(*args, **kwargs)
        if not submission.publishes_credit:
            del self.fields["credit_name"]
