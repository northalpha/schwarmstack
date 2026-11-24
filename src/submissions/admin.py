"""Admin der Betreiber: Aktion pflegen, Abgaben und Master ansehen und korrigieren (Ticket #29).

Rückzug, Widerruf und Master löschen sind Fachverhalten (`services`); der Admin fragt nach,
löst sie aus und schreibt jeden Eingriff ins Protokoll (Djangos `LogEntry`).
"""

from decimal import ROUND_HALF_UP, Decimal

from django import forms
from django.contrib import admin, messages
from django.db.models import Count, Prefetch, Q
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.template.defaultfilters import filesizeformat, truncatechars
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.decorators import method_decorator
from django.utils.html import format_html, format_html_join
from django.views.decorators.http import require_http_methods

from schwarmstack.models import ProtocolEntry
from schwarmstack.operator_site import site
from storage import get_storage

from . import services, uploads
from .models import Campaign, Consent, Master, Phase, Submission

# -- Aktion --------------------------------------------------------------------


GIB = 1024**3
MIB = 1024**2


class SizeField(forms.DecimalField):
    """Größe in GiB oder MiB im Formular, in Bytes im Modell (wie `manage.py campaign`)."""

    def __init__(self, *, unit: int, **kwargs):
        self.unit = unit
        kwargs.setdefault("localize", True)
        super().__init__(**kwargs)

    def prepare_value(self, value):
        if isinstance(value, int):
            # Ganze Zahlen ohne Nachkommastellen zeigen, sonst so genau wie nötig.
            value = (Decimal(value) / self.unit).normalize()
            return value.quantize(Decimal(1)) if value == value.to_integral() else value
        return value

    def to_python(self, value):
        value = super().to_python(value)
        if value is None:
            return None
        return int((value * self.unit).to_integral_value(rounding=ROUND_HALF_UP))

    def validate(self, value):
        forms.Field.validate(self, value)
        if value is not None and value <= 0:
            raise forms.ValidationError("Die Größe muss größer als 0 sein.", code="min_value")

    def run_validators(self, value):
        # Die Validatoren der DecimalField prüfen Stellen einer Dezimalzahl, hier steht Bytes.
        pass


class CampaignForm(forms.ModelForm):
    quota = SizeField(unit=GIB, label="Quote je Abgabe (GiB)")
    global_cap = SizeField(unit=GIB, label="Gesamtgrenze (GiB)")
    max_master_size = SizeField(unit=MIB, label="Höchstgröße je Master (MiB)")

    class Meta:
        model = Campaign
        fields = [
            "object_name",
            "starts_at",
            "ends_at",
            "grace_period",
            "quota",
            "global_cap",
            "max_master_size",
        ]

    # Ende nach Beginn prüft `Campaign.clean()`, das die ModelForm selbst aufruft.
    def clean_global_cap(self):
        global_cap = self.cleaned_data["global_cap"]
        uploads.check_global_cap(global_cap)
        return global_cap


@admin.register(Campaign, site=site)
class CampaignAdmin(admin.ModelAdmin):
    """Genau eine Aktion (ADR 0004): weder anlegen noch löschen, nur ändern."""

    form = CampaignForm
    fields = [
        "object_name",
        "starts_at",
        "ends_at",
        "grace_period",
        "quota",
        "global_cap",
        "max_master_size",
        "current_usage",
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        readonly = ["current_usage"]
        if obj is not None and obj.phase() is not Phase.BEFORE:
            # Nach dem Start soll niemand versehentlich die laufende Aktion verbiegen.
            readonly += ["object_name", "starts_at"]
        return readonly

    @admin.display(description="Belegung")
    def current_usage(self, obj):
        return filesizeformat(uploads.usage(Master.objects.all()))

    def changelist_view(self, request, extra_context=None):
        campaign = Campaign.current()
        if campaign is None:
            return super().changelist_view(request, extra_context)
        return redirect("operator:submissions_campaign_change", campaign.pk)


# -- Abgaben -------------------------------------------------------------------


def _with_masters(**condition):
    return Master.objects.filter(**condition).values("submission")


class ChannelFilter(admin.SimpleListFilter):
    title = "Kanal"
    parameter_name = "kanal"

    def lookups(self, request, model_admin):
        return Master.Channel.choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(
                pk__in=_with_masters(channel=self.value(), state=Master.State.ACCEPTED)
            )
        return queryset


class _YesNoFilter(admin.SimpleListFilter):
    def lookups(self, request, model_admin):
        return [("ja", "ja"), ("nein", "nein")]

    def condition(self) -> Q:
        raise NotImplementedError

    def queryset(self, request, queryset):
        if self.value() == "ja":
            return queryset.filter(self.condition())
        if self.value() == "nein":
            return queryset.exclude(self.condition())
        return queryset


class DuplicatesFilter(_YesNoFilter):
    title = "hat Dubletten"
    parameter_name = "dubletten"

    def condition(self):
        return Q(pk__in=_with_masters(state=Master.State.ACCEPTED, duplicate_of__isnull=False))


class RejectionsFilter(_YesNoFilter):
    title = "hat Ablehnungen"
    parameter_name = "ablehnungen"

    def condition(self):
        return Q(pk__in=_with_masters(state=Master.State.REJECTED))


class WithdrawnFilter(_YesNoFilter):
    title = "zurückgezogen"
    parameter_name = "zurueckgezogen"

    def condition(self):
        return Q(withdrawn_at__isnull=False)


def _change_url(submission_id):
    return reverse("operator:submissions_submission_change", args=[submission_id])


def _master_label(master):
    return f"{master.get_channel_display()} {master.original_name}"


def _master_size(master):
    return filesizeformat(master.size or master.declared_size)


class MasterInline(admin.TabularInline):
    model = Master
    fk_name = "submission"
    extra = 0
    can_delete = False
    fields = [
        "channel",
        "original_name",
        "size_display",
        "state",
        "rejection_reason",
        "sha256",
        "duplicate_link",
        "actions_links",
    ]
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Größe")
    def size_display(self, master):
        return _master_size(master)

    @admin.display(description="Dublette von")
    def duplicate_link(self, master):
        original = master.duplicate_of
        if original is None:
            return "–"
        url = _change_url(original.submission_id)
        return format_html('<a href="{}">{}</a>', url, original.submission.reference)

    @admin.display(description="Aktionen")
    def actions_links(self, master):
        links = []
        if master.state == Master.State.ACCEPTED:
            links.append((_master_url("download", master), "Herunterladen"))
        if master.state in services.DELETABLE:
            links.append((_master_url("delete", master), "Löschen …"))
        return format_html_join(" · ", '<a href="{}">{}</a>', links) or "–"


class ConsentInline(admin.TabularInline):
    """Einwilligungen sind nicht änderbar. Betreiber erteilen keine, sie vermerken nur Widerrufe."""

    model = Consent
    extra = 0
    can_delete = False
    fields = ["kind", "granted_at", "text_version", "revoked_at", "revoke_link"]
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="")
    def revoke_link(self, consent):
        if consent.revoked_at is not None:
            return "–"
        url = reverse(
            "operator:submissions_submission_consent_revoke",
            args=[consent.submission_id, consent.pk],
        )
        return format_html('<a href="{}">Widerruf vermerken …</a>', url)


def _master_url(action, master):
    return reverse(
        f"operator:submissions_submission_master_{action}",
        args=[master.submission_id, master.public_id],
    )


@admin.register(Submission, site=site)
class SubmissionAdmin(admin.ModelAdmin):
    change_form_template = "admin/submissions/submission/change_form.html"
    search_fields = ["reference", "credit_name"]
    list_display = [
        "reference",
        "credit_display",
        "setup_short",
        "master_count",
        "channels",
        "used_display",
        "has_duplicates",
        "is_withdrawn",
        "created_at",
    ]
    list_filter = [ChannelFilter, DuplicatesFilter, RejectionsFilter, WithdrawnFilter]
    inlines = [MasterInline, ConsentInline]
    fields = [
        "reference",
        "credit_name",
        "setup_description",
        "created_at",
        "withdrawn_at",
        "withdrawn_by",
    ]

    def get_queryset(self, request):
        accepted = Q(masters__state=Master.State.ACCEPTED)
        return (
            super()
            .get_queryset(request)
            .annotate(
                n_accepted=Count("masters", filter=accepted),
                n_duplicates=Count(
                    "masters", filter=accepted & Q(masters__duplicate_of__isnull=False)
                ),
                used=uploads.submission_usage(),
            )
            .prefetch_related(
                Prefetch(
                    "masters",
                    queryset=Master.objects.filter(state=Master.State.ACCEPTED),
                    to_attr="accepted_masters",
                )
            )
        )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change and form.changed_data:
            services.details_corrected(obj)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False  # Löschen heißt Rückzug, und der hat seine eigene Seite.

    def get_fields(self, request, obj=None):
        if obj is not None and not obj.publishes_credit:
            # Ohne Einwilligung zur Veröffentlichung keine Nennung, auch nicht nachträglich
            # (services.details_corrected): statt des Feldes nur „anonym“ (Ticket #33).
            return ["credit_display" if f == "credit_name" else f for f in self.fields]
        return self.fields

    def get_readonly_fields(self, request, obj=None):
        readonly = ["reference", "credit_display", "created_at", "withdrawn_at", "withdrawn_by"]
        if obj is not None and obj.is_withdrawn:
            readonly += ["credit_name", "setup_description"]
        return readonly

    @admin.display(description="Nennung", ordering="credit_name")
    def credit_display(self, submission):
        return submission.credit_name or "anonym"

    @admin.display(description="Setup")
    def setup_short(self, submission):
        return truncatechars(submission.setup_description, 40)

    @admin.display(description="Master", ordering="n_accepted")
    def master_count(self, submission):
        return submission.n_accepted

    @admin.display(description="Kanäle")
    def channels(self, submission):
        labels = {m.get_channel_display() for m in submission.accepted_masters}
        return ", ".join(sorted(labels)) or "–"

    @admin.display(description="Belegung", ordering="used")
    def used_display(self, submission):
        return filesizeformat(submission.used)

    @admin.display(description="Dubletten", boolean=True)
    def has_duplicates(self, submission):
        return submission.n_duplicates > 0

    @admin.display(description="zurückgezogen", boolean=True, ordering="withdrawn_at")
    def is_withdrawn(self, submission):
        return submission.is_withdrawn

    # -- Eingriffe im Auftrag der Teilnehmenden ---------------------------------

    def get_urls(self):
        view = self.admin_site.admin_view
        return [
            path(
                "<int:pk>/zurueckziehen/",
                view(self.withdraw_view),
                name="submissions_submission_withdraw",
            ),
            path(
                "<int:pk>/master/<uuid:master_id>/loeschen/",
                view(self.delete_master_view),
                name="submissions_submission_master_delete",
            ),
            path(
                "<int:pk>/master/<uuid:master_id>/download/",
                view(self.download_view),
                name="submissions_submission_master_download",
            ),
            path(
                "<int:pk>/einwilligung/<int:consent_id>/widerrufen/",
                view(self.revoke_view),
                name="submissions_submission_consent_revoke",
            ),
            *super().get_urls(),
        ]

    def _confirm(self, request, submission, *, title, question, details=(), button):
        return TemplateResponse(
            request,
            "admin/submissions/confirm.html",
            {
                **self.admin_site.each_context(request),
                "opts": self.opts,
                "original": submission,
                "title": title,
                "question": question,
                "details": details,
                "button": button,
                "cancel_url": _change_url(submission.pk),
            },
        )

    def _submission(self, request, pk):
        if not self.has_change_permission(request):
            raise Http404
        return get_object_or_404(Submission, pk=pk)

    @method_decorator(require_http_methods(["GET", "POST"]))
    def withdraw_view(self, request, pk):
        submission = self._submission(request, pk)
        if request.method == "POST":
            if not submission.is_withdrawn:
                services.withdraw(submission, by=Submission.WithdrawnBy.OPERATOR)
                self.log_change(request, submission, "Abgabe zurückgezogen")
                self.message_user(request, f"Abgabe {submission} wurde zurückgezogen.")
            return HttpResponseRedirect(_change_url(submission.pk))
        return self._confirm(
            request,
            submission,
            title=f"Abgabe {submission} zurückziehen",
            question=(
                "Alle Master, Angaben und Einwilligungen dieser Abgabe werden endgültig gelöscht. "
                "Es bleibt nur die Abgabe-Kennung. Die Abgabe lässt sich nicht wieder öffnen."
            ),
            details=[str(m) for m in submission.masters.filter(state__in=services.DELETABLE)],
            button="Ja, zurückziehen",
        )

    def _master(self, request, pk, master_id):
        submission = self._submission(request, pk)
        return get_object_or_404(Master, submission=submission, public_id=master_id)

    @method_decorator(require_http_methods(["GET", "POST"]))
    def delete_master_view(self, request, pk, master_id):
        master = self._master(request, pk, master_id)
        if master.state not in services.DELETABLE:
            raise Http404
        submission = master.submission
        if request.method == "POST":
            description = _master_label(master)
            services.delete_master(master)
            self.log_change(request, submission, f"Master {description} gelöscht")
            self.message_user(request, f"Master {description} wurde gelöscht.")
            return HttpResponseRedirect(_change_url(submission.pk))
        return self._confirm(
            request,
            submission,
            title=f"Master aus {submission} löschen",
            question=(
                "Dieser Master wird sofort und endgültig aus dem Speicher gelöscht."
                + (
                    " Der laufende Upload wird abgebrochen."
                    if master.state == Master.State.UPLOADING
                    else ""
                )
            ),
            details=[
                " · ".join(
                    [
                        master.get_channel_display(),
                        master.original_name,
                        _master_size(master),
                        master.get_state_display(),
                    ]
                )
            ],
            button="Ja, löschen",
        )

    def download_view(self, request, pk, master_id):
        master = self._master(request, pk, master_id)
        if master.state != Master.State.ACCEPTED:
            raise Http404
        url = get_storage().download_url(master.key)
        self.log_change(
            request,
            master.submission,
            f"Master {_master_label(master)} heruntergeladen",
        )
        return HttpResponseRedirect(url)

    @method_decorator(require_http_methods(["GET", "POST"]))
    def revoke_view(self, request, pk, consent_id):
        submission = self._submission(request, pk)
        consent = get_object_or_404(Consent, pk=consent_id, submission=submission)
        withdraws = services.revocation_withdraws(consent)
        if request.method == "POST":
            label = consent.get_kind_display()
            if services.revoke(consent, by=Submission.WithdrawnBy.OPERATOR):
                self.log_change(request, submission, f"Widerruf vermerkt: {label}")
                if withdraws:
                    self.log_change(request, submission, "Abgabe zurückgezogen (nach Widerruf)")
                self.message_user(request, f"Widerruf vermerkt: {label}.", messages.SUCCESS)
            return HttpResponseRedirect(_change_url(submission.pk))
        question = f"Widerruf der Einwilligung „{consent.get_kind_display()}“ vermerken?"
        if withdraws:
            question += (
                " Ohne diese Einwilligung kann die Abgabe nicht bleiben: Sie wird zurückgezogen, "
                "alle Master und Angaben werden endgültig gelöscht."
            )
        else:
            question += (
                " Die Nennung wird gelöscht und aus den Begleitdateien entfernt; die Abgabe "
                "bleibt anonym. Die Einwilligung bleibt mit dem Zeitpunkt des Widerrufs stehen."
            )
        return self._confirm(
            request,
            submission,
            title=f"Widerruf für {submission}",
            question=question,
            button="Ja, Widerruf vermerken",
        )


# -- Master (Liste, z. B. abgelehnte nach Kategorie) ---------------------------


@admin.register(Master, site=site)
class MasterAdmin(admin.ModelAdmin):
    list_display = [
        "submission_link",
        "channel",
        "original_name",
        "size",
        "state",
        "rejection_category",
        "rejection_reason",
        "created_at",
    ]
    list_filter = ["state", "rejection_category", "channel"]
    search_fields = ["submission__reference", "original_name", "sha256"]
    list_select_related = ["submission"]
    list_display_links = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Abgabe", ordering="submission__reference")
    def submission_link(self, master):
        url = _change_url(master.submission_id)
        return format_html('<a href="{}">{}</a>', url, master.submission.reference)


# -- Protokoll -----------------------------------------------------------------


@admin.register(ProtocolEntry, site=site)
class ProtocolAdmin(admin.ModelAdmin):
    """Wer hat wann was geändert, gelöscht, zurückgezogen oder heruntergeladen."""

    list_display = ["action_time", "user", "object_repr", "action_flag", "message"]
    list_filter = ["user", "action_flag"]
    search_fields = ["object_repr", "change_message"]
    date_hierarchy = "action_time"
    list_display_links = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Änderung")
    def message(self, entry):
        return entry.get_change_message()
