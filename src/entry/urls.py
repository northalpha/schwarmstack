from django.urls import path

from . import views

urlpatterns = [
    path("start/<slug:slug>/", views.start, name="start"),
]
