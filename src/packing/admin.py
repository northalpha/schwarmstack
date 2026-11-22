from django.contrib import admin

from .models import PackJob


@admin.register(PackJob)
class PackJobAdmin(admin.ModelAdmin):
    list_display = ("stack", "kind", "state", "attempts", "created_at")
    list_filter = ("kind", "state")
    readonly_fields = [f.name for f in PackJob._meta.fields]

    def has_add_permission(self, request):
        return False
