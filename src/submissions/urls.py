from django.urls import path

from . import views

urlpatterns = [
    path("", views.entry, name="entry"),
    path("neu/", views.new_submission, name="new_submission"),
    path("abgabe/<str:reference>/", views.submission, name="submission"),
]
