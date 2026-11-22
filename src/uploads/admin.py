from django.contrib import admin

from .models import UploadedFile


@admin.register(UploadedFile)
class UploadedFileAdmin(admin.ModelAdmin):
    list_display = ("filename", "stack", "size_bytes", "format", "state", "created_at")
    list_filter = ("state", "format")
    search_fields = ("filename", "tus_id")
    # Dateien entstehen nur über tusd und den Worker, im Admin nur ansehen
    readonly_fields = [f.name for f in UploadedFile._meta.fields]

    def has_add_permission(self, request):
        return False
