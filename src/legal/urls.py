from django.urls import path

from . import views

urlpatterns = [
    path("datenschutz/", views.datenschutz, name="datenschutz"),
    path("impressum/", views.impressum, name="impressum"),
]
