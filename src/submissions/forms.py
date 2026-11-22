from urllib.parse import urlparse

from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory

from altcha_gate.forms import AltchaFormMixin

from .models import MAX_SOCIAL_LINKS, ExposureLine, Stack


class ParticipationForm(AltchaFormMixin, forms.Form):
    """Teilnahmeformular. Pflicht: Name und die beiden Einwilligungen privacy_read, project_use."""

    display_name = forms.CharField(label="Anzeigename / Credit", min_length=2, max_length=80)
    email = forms.EmailField(label="E-Mail (optional)", required=False)
    region = forms.CharField(label="Region (optional)", max_length=80, required=False)
    bortle = forms.IntegerField(
        label="Bortle-Klasse (optional)", min_value=1, max_value=9, required=False
    )
    privacy_read = forms.BooleanField(
        label="Ich habe die Datenschutzhinweise gelesen.",
        error_messages={
            "required": "Bitte bestätige, dass du die Datenschutzhinweise gelesen hast."
        },
    )
    project_use = forms.BooleanField(
        label="Ich bin damit einverstanden, dass meine Aufnahmen im Projekt verwendet werden.",
        error_messages={
            "required": "Ohne diese Einwilligung können wir deine Aufnahmen nicht annehmen."
        },
    )
    publish_name_links = forms.BooleanField(
        label="Mein Name und meine Links dürfen bei Veröffentlichungen genannt werden (optional).",
        required=False,
    )
    publish_equipment_photo = forms.BooleanField(
        label="Mein Equipment-Foto darf gezeigt werden (optional).", required=False
    )
    status_mails = forms.BooleanField(
        label="Ich möchte Status-Mails erhalten (optional, jederzeit widerrufbar).",
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for i in range(1, MAX_SOCIAL_LINKS + 1):
            self.fields[f"link{i}"] = forms.URLField(
                label=f"Link {i} (optional, https)",
                max_length=300,
                required=False,
                assume_scheme="https",
            )

    def clean_display_name(self):
        return self.cleaned_data["display_name"].strip()

    def _clean_link(self, i):
        url = self.cleaned_data.get(f"link{i}", "")
        if url and urlparse(url).scheme != "https":
            self.add_error(f"link{i}", "Nur Links mit https:// sind erlaubt.")
        return url

    def clean(self):
        cleaned = super().clean()
        for i in range(1, MAX_SOCIAL_LINKS + 1):
            self._clean_link(i)
        if cleaned.get("status_mails") and not cleaned.get("email"):
            self.add_error("email", "Für Status-Mails brauchen wir deine E-Mail-Adresse.")
        return cleaned

    @property
    def links(self) -> list[str]:
        return [
            u for i in range(1, MAX_SOCIAL_LINKS + 1) if (u := self.cleaned_data.get(f"link{i}"))
        ]


class StackForm(forms.ModelForm):
    class Meta:
        model = Stack
        fields = (
            "object_name",
            "capture_dates",
            "description",
            "telescope",
            "focal_length_mm",
            "aperture_mm",
            "reducer_barlow",
            "camera",
            "mount",
            "filters",
            "has_darks",
            "has_flats",
            "has_bias",
            "has_darkflats",
            "notes",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class BaseExposureFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        if not any(form.has_changed() for form in self.forms):
            raise ValidationError("Bitte mindestens eine Belichtungszeile ausfüllen.")


ExposureFormSet = inlineformset_factory(
    Stack,
    ExposureLine,
    formset=BaseExposureFormSet,
    fields=("filter", "count", "seconds", "gain_iso", "sensor_temp_c"),
    extra=4,
    can_delete=False,
)

# Felder, die aus dem letzten Stack vorausgefüllt werden (Ausrüstung bleibt meist gleich)
PREFILL_FIELDS = (
    "telescope",
    "focal_length_mm",
    "aperture_mm",
    "reducer_barlow",
    "camera",
    "mount",
    "filters",
    "has_darks",
    "has_flats",
    "has_bias",
    "has_darkflats",
)
