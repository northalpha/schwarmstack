"""Aktion pflegen im Admin (Ticket #29)."""

from datetime import timedelta

import pytest
from admin_helper import ADMIN, change_form_data, operator, operator_client  # noqa: F401
from django.utils import timezone
from files import fits
from uploads_helper import upload

from submissions.models import Campaign, Submission

pytestmark = pytest.mark.django_db

GIB = 1024**3


def url(campaign):
    return f"{ADMIN}submissions/campaign/{campaign.pk}/change/"


def save(client, campaign, **changes):
    form = client.get(url(campaign))
    return client.post(url(campaign), change_form_data(form, **changes))


def test_aktion_weder_anlegen_noch_loeschen(operator_client, campaign):  # noqa: F811
    assert operator_client.get(f"{ADMIN}submissions/campaign/add/").status_code == 403
    assert (
        operator_client.get(f"{ADMIN}submissions/campaign/{campaign.pk}/delete/").status_code == 403
    )


def test_liste_fuehrt_zur_einen_aktion(operator_client, campaign):  # noqa: F811
    response = operator_client.get(f"{ADMIN}submissions/campaign/")
    assert response.status_code == 302
    assert response["Location"] == url(campaign)


def test_grenzen_und_zeiten_lassen_sich_aendern(operator_client, campaign):  # noqa: F811
    new_end = (campaign.ends_at + timedelta(days=7)).replace(microsecond=0)
    response = save(
        operator_client,
        campaign,
        ends_at_0=timezone.localtime(new_end).strftime("%d.%m.%Y"),
        ends_at_1=timezone.localtime(new_end).strftime("%H:%M:%S"),
        grace_period="03:00:00",
        quota=str(3 * GIB),
        global_cap=str(500 * GIB),
        max_master_size=str(800 * 1024**2),
    )
    assert response.status_code == 302, response.context["adminform"].form.errors
    campaign.refresh_from_db()
    assert campaign.ends_at == new_end
    assert campaign.grace_period == timedelta(hours=3)
    assert campaign.quota == 3 * GIB
    assert campaign.global_cap == 500 * GIB
    assert campaign.max_master_size == 800 * 1024**2


def test_objekt_und_beginn_nach_dem_start_gesperrt(operator_client, campaign):  # noqa: F811
    starts_at = campaign.starts_at
    save(operator_client, campaign, object_name="M 31", starts_at_0="01.01.2020")
    campaign.refresh_from_db()
    assert campaign.object_name == "M 101"
    assert campaign.starts_at == starts_at


def test_objekt_vor_dem_start_aenderbar(operator_client, campaign):  # noqa: F811
    campaign.starts_at = timezone.now() + timedelta(days=1)
    campaign.save()
    response = save(operator_client, campaign, object_name="M 31")
    assert response.status_code == 302
    campaign.refresh_from_db()
    assert campaign.object_name == "M 31"


def test_gesamtgrenze_nicht_unter_der_belegung(
    operator_client,  # noqa: F811
    campaign,
    client,
    valid_form,
    settings,
    tmp_path,
):
    settings.STORAGE_LOCAL_DIR = tmp_path
    client.post("/", valid_form)
    data = fits()
    upload(client, Submission.objects.get().reference, data)

    response = save(operator_client, campaign, global_cap=str(len(data) - 1))
    assert response.status_code == 200
    assert "Belegung" in str(response.context["adminform"].form.errors["global_cap"])
    campaign.refresh_from_db()
    assert campaign.global_cap == 400 * GIB

    assert save(operator_client, campaign, global_cap=str(len(data))).status_code == 302


def test_aenderung_steht_im_protokoll(operator_client, campaign, operator):  # noqa: F811
    from django.contrib.admin.models import LogEntry

    save(operator_client, campaign, quota=str(3 * GIB))
    entry = LogEntry.objects.get()
    assert entry.user == operator
    assert entry.object_id == str(campaign.pk)
    assert Campaign.objects.get().quota == 3 * GIB
