from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("healthz", views.healthz, name="healthz"),
    path("altcha/", include("altcha_gate.urls")),
    path("", include("entry.urls")),
    path("", include("submissions.urls")),
    path("", include("legal.urls")),
    path(f"{settings.ADMIN_PATH}/", admin.site.urls),
]
