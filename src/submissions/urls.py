from django.urls import path

from . import api, views

urlpatterns = [
    path("", views.entry, name="entry"),
    path("neu/", views.new_submission, name="new_submission"),
    path("abgabe/<str:reference>/", views.submission, name="submission"),
    path("abgabe/<str:reference>/zurueckziehen/", views.withdraw, name="withdraw"),
    path("abgabe/<str:reference>/master/", api.start, name="upload_start"),
    path(
        "abgabe/<str:reference>/master/<uuid:master_id>/loeschen/",
        views.delete_master,
        name="delete_master",
    ),
    path(
        "abgabe/<str:reference>/master/<uuid:master_id>/signieren/",
        api.sign,
        name="upload_sign",
    ),
    path(
        "abgabe/<str:reference>/master/<uuid:master_id>/abbrechen/",
        api.abort,
        name="upload_abort",
    ),
    path(
        "abgabe/<str:reference>/master/<uuid:master_id>/fertig/",
        api.finish,
        name="upload_finish",
    ),
]
