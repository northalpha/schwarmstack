from django.urls import path

from . import views

urlpatterns = [
    path("challenge/", views.challenge, name="altcha_challenge"),
]
