from django.contrib import admin

from .models import EntryAttempt


@admin.register(EntryAttempt)
class EntryAttemptAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event", "accepted")
    list_filter = ("accepted", "event")
    readonly_fields = [f.name for f in EntryAttempt._meta.fields]

    def has_add_permission(self, request):
        return False
