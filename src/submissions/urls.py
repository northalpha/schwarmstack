from django.urls import path

from . import views

urlpatterns = [
    path("teilnahme/<slug:slug>/", views.teilnahme, name="teilnahme"),
    path("a/<str:token>/", views.abgabe_link, name="abgabe_link"),
    path("abgabe/", views.abgabe, name="abgabe"),
]
