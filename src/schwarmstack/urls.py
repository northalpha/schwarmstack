from django.conf import settings
from django.urls import include, path

from .health import healthz

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("", include("submissions.urls")),
]

if settings.STORAGE_BACKEND == "local":
    from storage.local_views import local_s3

    urlpatterns.append(path("_lokal/s3/<str:token>/", local_s3, name="local_s3"))
