from django.conf import settings
from django.urls import include, path

import submissions.admin  # noqa: F401  (registriert die Modelle am Admin der Betreiber)

from .health import healthz
from .operator_site import site

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path(f"{settings.ADMIN_PATH}/", site.urls),
    path("", include("submissions.urls")),
]

if settings.STORAGE_BACKEND == "local":
    from storage.local_views import local_s3

    urlpatterns.append(path("_lokal/s3/<str:token>/", local_s3, name="local_s3"))
