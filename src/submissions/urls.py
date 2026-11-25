from django.urls import path, re_path

from . import api, public, views

urlpatterns = [
    path("", views.entry, name="entry"),
    path("zahlen.json", public.community_numbers_view, name="community_numbers"),
    path("neu/", views.new_submission, name="new_submission"),
    path("datenschutz/", views.privacy_notice, name="privacy_notice"),
    path("datenschutz/<str:version>/", views.privacy_notice, name="privacy_notice_version"),
    path("submission/<str:reference>/", views.submission, name="submission"),
    path("submission/<str:reference>/aendern/", views.change_details, name="change_details"),
    path("submission/<str:reference>/aendern/foto/", views.change_photo, name="change_photo"),
    path(
        "submission/<str:reference>/aendern/foto/loeschen/",
        views.delete_photo,
        name="delete_photo",
    ),
    path("submission/<str:reference>/foto/", views.photo, name="photo"),
    path(
        "submission/<str:reference>/foto/vorschau/",
        views.photo_thumbnail,
        name="photo_thumbnail",
    ),
    path(
        "submission/<str:reference>/loeschen/",
        views.delete_submission,
        name="delete_submission",
    ),
    path(
        "submission/<str:reference>/namensnennung/widerrufen/",
        views.revoke_credit,
        name="revoke_credit",
    ),
    path(
        "submission/<str:reference>/namensnennung/erlauben/",
        views.grant_credit,
        name="grant_credit",
    ),
    path("submission/<str:reference>/master/", api.start, name="upload_start"),
    path(
        "submission/<str:reference>/master/<uuid:master_id>/loeschen/",
        views.delete_master,
        name="delete_master",
    ),
    path(
        "submission/<str:reference>/master/<uuid:master_id>/signieren/",
        api.sign,
        name="upload_sign",
    ),
    path(
        "submission/<str:reference>/master/<uuid:master_id>/abbrechen/",
        api.abort,
        name="upload_abort",
    ),
    path(
        "submission/<str:reference>/master/<uuid:master_id>/fertig/",
        api.finish,
        name="upload_finish",
    ),
    path(
        "submission/<str:reference>/master/<uuid:master_id>/belichtung/",
        api.change_exposure,
        name="exposure",
    ),
    # Alte Adressen vor der Umbenennung (Issue #66): dauerhaft auf `submission/` umleiten.
    re_path(r"^abgabe/(?P<rest>.+)$", views.legacy_redirect, name="legacy_submission"),
]
