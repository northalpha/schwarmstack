from django.contrib import admin, messages

from packing.services import enqueue_pack
from uploads.models import UploadedFile

from .models import Consent, Event, ExposureLine, SocialLink, Stack, Submission
from .quota import used_bytes_event, used_bytes_submission


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "active", "opens_at", "closes_at", "belegt")
    list_filter = ("active",)
    prepopulated_fields = {"slug": ("title",)}
    fieldsets = (
        (None, {"fields": ("title", "slug", "description", "active", "opens_at", "closes_at")}),
        ("Einstieg über die Projektwebsite", {"fields": ("entry_origins", "entry_page_url")}),
        (
            "Grenzen",
            {"fields": ("quota_bytes_per_submission", "global_cap_bytes", "max_file_bytes")},
        ),
        (
            "Verarbeitung",
            {
                "fields": (
                    "use_fpack",
                    "delete_originals_after_pack",
                    "auto_close_after_idle_minutes",
                )
            },
        ),
        ("Missbrauchsschutz", {"fields": ("altcha_enabled",)}),
    )

    @admin.display(description="Belegt (GiB)")
    def belegt(self, obj: Event) -> str:
        return f"{used_bytes_event(obj) / 1024**3:.2f} / {obj.global_cap_bytes / 1024**3:.0f}"


class SocialLinkInline(admin.TabularInline):
    model = SocialLink
    extra = 0
    max_num = 4
    readonly_fields = ("platform",)


class ConsentInline(admin.TabularInline):
    model = Consent
    extra = 0
    readonly_fields = ("granted_at", "revoked_at", "text_version")


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("display_name", "event", "created_at", "is_blocked", "belegt")
    list_filter = ("event", "is_blocked")
    search_fields = ("display_name", "email")
    readonly_fields = ("id", "token_hash", "ip_hash", "created_at", "last_seen_at")
    inlines = [SocialLinkInline, ConsentInline]
    actions = ["sperren", "entsperren"]

    @admin.display(description="Belegt (MiB)")
    def belegt(self, obj: Submission) -> str:
        return f"{used_bytes_submission(obj) / 1024**2:.0f}"

    @admin.action(description="Ausgewählte Abgaben sperren")
    def sperren(self, request, queryset):
        count = queryset.update(is_blocked=True)
        self.message_user(request, f"{count} Abgabe(n) gesperrt.", messages.SUCCESS)

    @admin.action(description="Ausgewählte Abgaben entsperren")
    def entsperren(self, request, queryset):
        count = queryset.update(is_blocked=False)
        self.message_user(request, f"{count} Abgabe(n) entsperrt.", messages.SUCCESS)


class ExposureLineInline(admin.TabularInline):
    model = ExposureLine
    extra = 0


class UploadedFileInline(admin.TabularInline):
    model = UploadedFile
    extra = 0
    can_delete = False
    fields = ("filename", "size_bytes", "format", "state", "reject_reason")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Stack)
class StackAdmin(admin.ModelAdmin):
    list_display = ("object_name", "submission", "state", "last_upload_at")
    list_filter = ("state", "submission__event")
    search_fields = ("object_name", "submission__display_name")
    readonly_fields = (
        "id",
        "packed_key",
        "packed_bytes",
        "original_bytes",
        "sha256_archive",
        "header_summary",
        "closed_at",
        "last_upload_at",
    )
    inlines = [ExposureLineInline, UploadedFileInline]
    actions = ["wieder_oeffnen", "neu_packen"]

    @admin.action(description="Ausgewählte Stacks wieder öffnen")
    def wieder_oeffnen(self, request, queryset):
        count = queryset.update(state=Stack.OPEN, closed_at=None, error_message="")
        self.message_user(request, f"{count} Stack(s) geöffnet.", messages.SUCCESS)

    @admin.action(description="Ausgewählte Stacks neu packen")
    def neu_packen(self, request, queryset):
        for stack in queryset:
            enqueue_pack(stack)
        self.message_user(request, f"{queryset.count()} Stack(s) eingeplant.", messages.SUCCESS)
