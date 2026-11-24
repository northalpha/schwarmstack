"""Export: Manifest und Download-Liste für die Betreiber, endgültiger Export (ADR 0008).

Ein vorläufiger Export ist jederzeit möglich und enthält nur das Manifest, ohne Links. Den
endgültigen Export gibt es genau einmal, frühestens nach Ende der Aktion plus Nachfrist; danach
stellt jedes Manifest und jede Download-Liste neue Links aus, bis die Löschfrist abläuft.
"""

from datetime import datetime, timedelta
from pathlib import PurePosixPath

from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone

from storage import get_storage

from .models import Campaign, Consent, Master, Phase, Submission

# Grenze vorsignierter S3-Links (SigV4): 7 Tage.
LINK_SECONDS = 7 * 24 * 3600


class ExportError(Exception):
    """Der endgültige Export ist (noch oder nicht mehr) nicht möglich; die Nachricht erklärt es."""


def _time(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def path(master: Master) -> str:
    """Zielpfad beim Herunterladen, z. B. `SW-7K3Q/Ha_3f9c1a2b.xisf`.

    Eingaben der Teilnehmenden fließen nicht ein; der Originalname steht nur im Manifest. Die
    Download-Liste legt die Namen fest, nicht die Objekt-Schlüssel.
    """
    suffix = PurePosixPath(master.key).suffix
    return f"{master.submission.reference}/{master.channel}_{master.public_id.hex[:8]}{suffix}"


def links_available(campaign: Campaign, now: datetime | None = None) -> bool:
    """Links gibt es nur nach dem endgültigen Export und bis zum Ablauf der Löschfrist."""
    now = now or timezone.now()
    return campaign.is_exported and campaign.deleted_at is None and now < campaign.deletes_at


def may_finalize(campaign: Campaign) -> str | None:
    """Warum der endgültige Export jetzt nicht geht, oder None, wenn er geht."""
    if campaign.is_exported:
        return "Der endgültige Export wurde bereits ausgelöst."
    if campaign.phase() is not Phase.CLOSED:
        return (
            "Den endgültigen Export gibt es erst nach Ende der Aktion plus Nachfrist "
            f"({timezone.localtime(campaign.closes_at):%d.%m.%Y %H:%M})."
        )
    return None


def finalize(campaign: Campaign) -> Campaign:
    """Endgültiger Export: friert alle Abgaben ein, auch für Betreiber, und startet die
    Löschfrist. Genau einmal möglich."""
    with transaction.atomic():
        campaign = Campaign.objects.select_for_update().get(pk=campaign.pk)
        refusal = may_finalize(campaign)
        if refusal:
            raise ExportError(refusal)
        campaign.exported_at = timezone.now()
        campaign.save(update_fields=["exported_at"])
    return campaign


def days_left(campaign: Campaign, now: datetime | None = None) -> int | None:
    """Wie viele Tage die Löschfrist noch läuft (angefangene Tage zählen), sonst None."""
    if not campaign.is_exported or campaign.deleted_at is not None:
        return None
    left = campaign.deletes_at - (now or timezone.now())
    return max(0, -(-left // timedelta(days=1)))


def manifest(campaign: Campaign, *, links: bool = False) -> dict:
    """Das Manifest: Aktion → Abgaben → angenommene Master.

    Mit `links` (nur nach dem endgültigen Export) bekommt jeder Master einen Download-Link,
    der 7 Tage gilt.
    """
    if links and not links_available(campaign):
        raise ExportError("Links gibt es nur nach dem endgültigen Export bis zur Löschung.")
    storage = get_storage() if links else None
    submissions = Submission.objects.order_by("created_at").prefetch_related(
        Prefetch("consents", queryset=Consent.objects.order_by("kind")),
        Prefetch(
            "masters",
            queryset=Master.objects.filter(state=Master.State.ACCEPTED)
            .select_related("submission", "duplicate_of__submission")
            .order_by("created_at"),
        ),
    )
    entries = []
    for submission in submissions:
        if submission.is_withdrawn:
            # Keine Kennung soll spurlos verschwinden.
            entries.append(
                {
                    "reference": submission.reference,
                    "withdrawn_at": _time(submission.withdrawn_at),
                    "amended_at": _time(submission.amended_at),
                }
            )
            continue
        consents = list(submission.consents.all())
        publishes = any(
            c.kind == Consent.Kind.PUBLISH_CREDIT and c.revoked_at is None for c in consents
        )
        entries.append(
            {
                "reference": submission.reference,
                "credit_name": (submission.credit_name or None) if publishes else None,
                "setup_description": submission.setup_description,
                "created_at": _time(submission.created_at),
                "amended_at": _time(submission.amended_at),
                "consents": [
                    {
                        "kind": c.kind,
                        "granted_at": _time(c.granted_at),
                        "text_version": c.text_version,
                        "revoked_at": _time(c.revoked_at),
                    }
                    for c in consents
                ],
                "masters": [_master(m, storage) for m in submission.masters.all()],
            }
        )
    return {
        "final": campaign.is_exported,
        "created_at": _time(timezone.now()),
        "campaign": {
            "object_name": campaign.object_name,
            "starts_at": _time(campaign.starts_at),
            "ends_at": _time(campaign.ends_at),
            "exported_at": _time(campaign.exported_at),
            "deletes_at": _time(campaign.deletes_at),
        },
        "links_valid_until": (
            _time(timezone.now() + timedelta(seconds=LINK_SECONDS)) if links else None
        ),
        "submissions": entries,
    }


def _master(master: Master, storage) -> dict:
    original = master.duplicate_of
    entry = {
        "master_id": master.public_id.hex,
        "channel": master.channel,
        "original_name": master.original_name,
        "size": master.size,
        "sha256": master.sha256,
        "duplicate_of": (
            {"reference": original.submission.reference, "master_id": original.public_id.hex}
            if original
            else None
        ),
        "path": path(master),
    }
    if storage is not None:
        entry["url"] = storage.download_url(master.key, seconds=LINK_SECONDS)
    return entry


def download_list(data: dict) -> str:
    """Download-Liste im Eingabeformat von `aria2c` (`aria2c -i liste.txt`): je Master Link,
    Zielpfad und Prüfsumme, die aria2c nach dem Laden abgleicht."""
    lines = []
    for submission in data["submissions"]:
        for master in submission.get("masters", []):
            lines.append(master["url"])
            lines.append(f"  out={master['path']}")
            if master["sha256"]:
                lines.append(f"  checksum=sha-256={master['sha256']}")
    return "\n".join(lines) + "\n" if lines else ""
