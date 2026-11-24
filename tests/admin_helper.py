"""Gemeinsames für die Tests des Admin (Ticket #29): angemeldet als Betreiber."""

import pytest
from django.test import Client

ADMIN = "/betrieb-test/"
PASSWORD = "sternenstaub-2026"


@pytest.fixture
def operator(db, django_user_model):
    return django_user_model.objects.create_superuser("ada", "ada@example.org", PASSWORD)


@pytest.fixture
def operator_client(operator):
    client = Client()
    client.force_login(operator)
    return client


def submission_url(submission, suffix="change/"):
    return f"{ADMIN}submissions/submission/{submission.pk}/{suffix}"


def master_url(master, action):
    return submission_url(master.submission, f"master/{master.public_id}/{action}/")


def change_form_data(response, **overrides):
    """POST-Daten eines Änderungsformulars im Admin, wie der Browser sie schicken würde."""
    from django.forms import MultiWidget

    data = {}
    form = response.context["adminform"].form
    for name in form.fields:
        bound = form[name]
        widget = bound.field.widget
        if isinstance(widget, MultiWidget):
            values = widget.decompress(bound.value())
            for index, (sub, value) in enumerate(zip(widget.widgets, values, strict=True)):
                data[f"{name}_{index}"] = sub.format_value(value) or ""
        else:
            value = bound.field.prepare_value(bound.value())
            if value is not None:
                data[name] = value
    for inline in response.context["inline_admin_formsets"]:
        management = inline.formset.management_form
        for name in management.fields:
            data[f"{management.prefix}-{name}"] = management.initial.get(name, 0)
        for index, sub in enumerate(inline.formset.forms):
            for name in sub.fields:
                # Das versteckte `id` steht nicht in `initial`, der Browser schickt es mit.
                value = sub.initial.get(name, sub[name].value())
                if value is not None:
                    data[f"{inline.formset.prefix}-{index}-{name}"] = value
    data.update(overrides)
    return data


def log_messages(obj=None):
    from django.contrib.admin.models import LogEntry

    entries = LogEntry.objects.order_by("action_time")
    if obj is not None:
        entries = entries.filter(object_id=str(obj.pk))
    return [entry.get_change_message() for entry in entries]
