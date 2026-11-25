from django import forms

from . import photos, services

PHOTO_CONSENT_LABEL = (
    "Ich erlaube, dass das Foto im Rahmen des Projekts verwendet wird. Ich habe den "
    "Datenschutzhinweis gelesen. Ich kann die Einwilligung jederzeit widerrufen, indem ich das "
    "Foto lösche."
)
PHOTO_ACCEPT = (
    "image/jpeg,image/png,image/webp,image/heic,image/heif,.jpg,.jpeg,.png,.webp,.heic,.heif"
)


def _photo_field(*, required=False, label="Equipment-Foto (freiwillig)"):
    return forms.FileField(
        label=label,
        required=required,
        widget=forms.FileInput(attrs={"accept": PHOTO_ACCEPT}),
        help_text="JPEG, PNG, WebP oder HEIC, höchstens 10 MB.",
        error_messages={"required": "Wähle ein Foto aus."},
    )


def _photo_consent_field(*, required=False):
    return forms.BooleanField(
        label=PHOTO_CONSENT_LABEL,
        required=required,
        error_messages={
            "required": "Pflichtangabe: Ohne deine Einwilligung speichern wir das Foto nicht."
        },
    )


class PhotoCleaning:
    """Gemeinsames der Formulare mit Equipment-Foto: Größe vor dem Dekodieren prüfen, die
    Einwilligung verlangen und das Foto bereinigen. Das Ergebnis steht in `photo`, die Datei der
    Teilnehmenden und ihr Name gelangen nirgends weiter."""

    photo: photos.CleanPhoto | None = None
    photo_consent_required = True

    def clean_equipment_photo(self):
        upload = self.cleaned_data["equipment_photo"]
        if upload and upload.size > photos.MAX_BYTES:
            raise forms.ValidationError("Das Foto ist größer als 10 MB.")
        return upload

    def clean_photo(self, cleaned):
        upload = cleaned.get("equipment_photo")
        if not upload:
            return
        if self.photo_consent_required and not cleaned.get("consent_equipment_photo"):
            self.add_error(
                "consent_equipment_photo",
                self.fields["consent_equipment_photo"].error_messages["required"],
            )
            return
        try:
            self.photo = photos.clean(upload)
        except photos.PhotoRejected as rejected:
            self.add_error("equipment_photo", str(rejected))


class SubmissionForm(PhotoCleaning, forms.Form):
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
    equipment_photo = _photo_field()
    consent_equipment_photo = _photo_consent_field()

    def clean(self):
        cleaned = super().clean()
        self.clean_photo(cleaned)
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


class PhotoForm(PhotoCleaning, forms.Form):
    """Equipment-Foto hinzufügen oder ersetzen. Das Häkchen zur Einwilligung ist Pflicht, solange
    keine gültige Einwilligung zur aktuellen Fassung des Hinweistextes vorliegt."""

    equipment_photo = _photo_field(required=True)
    consent_equipment_photo = _photo_consent_field(required=True)

    def __init__(self, *args, submission, **kwargs):
        super().__init__(*args, **kwargs)
        self.photo_consent_required = services.photo_consent_needed(submission)
        if not self.photo_consent_required:
            del self.fields["consent_equipment_photo"]
        self.replaces = submission.photo is not None
        if self.replaces:
            self.fields["equipment_photo"].label = "Neues Equipment-Foto"

    def clean(self):
        cleaned = super().clean()
        self.clean_photo(cleaned)
        return cleaned
