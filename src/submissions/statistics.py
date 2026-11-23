"""Statistik für die Betreiber: Stand der Aktion, bei jedem Aufruf frisch berechnet.

Zählt Abgaben, nie Personen. Nicht öffentlich: Sie erscheint nur im Admin.
"""

import datetime as dt
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.urls import reverse

from .models import Campaign, Master, Submission
from .uploads import release_stale
from .validation import Category

# Der Verlauf zählt Tage in der Zeit der Betreiber, nicht in UTC.
DAY_ZONE = ZoneInfo("Europe/Berlin")


@dataclass(frozen=True)
class ChannelRow:
    label: str
    count: int
    size: int


@dataclass(frozen=True)
class RejectionRow:
    label: str
    count: int
    url: str


@dataclass
class Day:
    day: dt.date
    new_submissions: int = 0
    accepted: int = 0
    withdrawals: int = 0


@dataclass
class Statistics:
    submissions_active: int
    submissions_withdrawn: int
    masters_by_state: list[tuple[str, int]]
    channels: list[ChannelRow]
    accepted: int
    reserved: int
    global_cap: int | None
    duplicates: int
    rejections: list[RejectionRow]
    days: list[Day] = field(default_factory=list)

    @property
    def used(self) -> int:
        """Belegung: angenommene Master plus Reservierungen laufender Uploads."""
        return self.accepted + self.reserved

    @property
    def used_percent(self) -> int | None:
        if not self.global_cap:
            return None
        return min(100, self.used * 100 // self.global_cap)

    @property
    def free(self) -> int | None:
        return None if self.global_cap is None else max(self.global_cap - self.used, 0)


def compute() -> Statistics:
    release_stale()
    campaign = Campaign.current()
    submissions = Submission.objects.aggregate(
        active=Count("pk", filter=Q(withdrawn_at__isnull=True)),
        withdrawn=Count("pk", filter=Q(withdrawn_at__isnull=False)),
    )
    by_state = dict(
        Master.objects.values_list("state").annotate(n=Count("pk")).values_list("state", "n")
    )
    accepted = Master.objects.filter(state=Master.State.ACCEPTED)
    totals = Master.objects.aggregate(
        accepted=Sum("size", filter=Q(state=Master.State.ACCEPTED)),
        reserved=Sum("declared_size", filter=Q(state=Master.State.UPLOADING)),
    )
    return Statistics(
        submissions_active=submissions["active"],
        submissions_withdrawn=submissions["withdrawn"],
        masters_by_state=[(label, by_state.get(value, 0)) for value, label in Master.State.choices],
        channels=_channels(accepted),
        accepted=totals["accepted"] or 0,
        reserved=totals["reserved"] or 0,
        global_cap=campaign.global_cap if campaign else None,
        duplicates=accepted.filter(duplicate_of__isnull=False).count(),
        rejections=_rejections(),
        days=_days(accepted),
    )


def _channels(accepted) -> list[ChannelRow]:
    rows = {
        row["channel"]: row
        for row in accepted.values("channel").annotate(n=Count("pk"), size=Sum("size"))
    }
    return [
        ChannelRow(label, rows[value]["n"], rows[value]["size"] or 0)
        for value, label in Master.Channel.choices
        if value in rows
    ]


def _rejections() -> list[RejectionRow]:
    counts = dict(
        Master.objects.filter(state=Master.State.REJECTED)
        .values_list("rejection_category")
        .annotate(n=Count("pk"))
        .values_list("rejection_category", "n")
    )
    changelist = reverse("operator:submissions_master_changelist")
    return [
        RejectionRow(
            category.label,
            counts.get(category.value, 0),
            f"{changelist}?state__exact=rejected&rejection_category__exact={category.value}",
        )
        for category in Category
    ]


def _days(accepted) -> list[Day]:
    """Verlauf nach heutigem Stand: Zurückgezogene Abgaben und gelöschte Master fehlen,
    die Zahl der Rückzüge steht getrennt daneben."""
    days: dict[dt.date, Day] = {}

    def row(day: dt.date) -> Day:
        return days.setdefault(day, Day(day))

    for item in (
        Submission.objects.filter(withdrawn_at__isnull=True)
        .annotate(day=TruncDate("created_at", tzinfo=DAY_ZONE))
        .values("day")
        .annotate(n=Count("pk"))
    ):
        row(item["day"]).new_submissions = item["n"]
    for item in (
        accepted.annotate(day=TruncDate("completed_at", tzinfo=DAY_ZONE))
        .values("day")
        .annotate(size=Sum("size"))
    ):
        row(item["day"]).accepted = item["size"] or 0
    for item in (
        Submission.objects.filter(withdrawn_at__isnull=False)
        .annotate(day=TruncDate("withdrawn_at", tzinfo=DAY_ZONE))
        .values("day")
        .annotate(n=Count("pk"))
    ):
        row(item["day"]).withdrawals = item["n"]
    return sorted(days.values(), key=lambda d: d.day, reverse=True)
