"""Freshness filters (posted date age)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable

from hanou_career.jobs.schema import NormalizedJob


def parse_posted(value: str | None) -> date | None:
    if not value:
        return None
    raw = str(value).strip()[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        try:
            return datetime.strptime(raw, "%d.%m.%Y").date()
        except ValueError:
            return None


def is_fresh(
    job: NormalizedJob,
    *,
    max_age_days: int,
    today: date | None = None,
    allow_missing_date: bool = True,
) -> bool:
    """True if posted recently, or date missing (and allowed — e.g. live-verified ATS)."""
    if max_age_days <= 0:
        return True
    posted = parse_posted(job.posted_date)
    if posted is None:
        return allow_missing_date
    cutoff = (today or date.today()) - timedelta(days=max_age_days)
    return posted >= cutoff


def filter_fresh(
    jobs: Iterable[NormalizedJob],
    *,
    max_age_days: int,
    allow_missing_date: bool = True,
) -> list[NormalizedJob]:
    return [
        j
        for j in jobs
        if is_fresh(j, max_age_days=max_age_days, allow_missing_date=allow_missing_date)
    ]
