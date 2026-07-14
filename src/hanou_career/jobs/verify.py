"""HTTP liveness checks for job URLs."""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

from hanou_career.jobs.schema import NormalizedJob

logger = logging.getLogger(__name__)

DEAD_MARKERS = (
    "nicht mehr verfügbar",
    "gibt es nicht oder nicht mehr",
    "stellenangebot wurde",
    "stelle wurde besetzt",
    "job not found",
    "seite nicht gefunden",
    "page not found",
    "stellenangebot nicht gefunden",
    "dieses stellenangebot gibt es nicht",
    "angebot ist nicht mehr aktiv",
    "position is no longer",
    "job is no longer available",
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}


def url_looks_alive(url: str, *, timeout: float = 20.0) -> bool:
    if not url or url.startswith("https://example."):
        return False
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=HEADERS) as client:
            # Prefer GET — many ATS boards dislike HEAD
            res = client.get(url)
    except httpx.HTTPError:
        return False
    if res.status_code in {404, 410, 451}:
        return False
    if res.status_code >= 400:
        return False
    body = res.text.lower()
    if any(m in body for m in DEAD_MARKERS):
        return False
    # Softgarden / career pages should have some substance
    if len(body) < 400:
        return False
    return True


def filter_live_jobs(
    jobs: list[NormalizedJob],
    *,
    max_workers: int = 16,
    skip_hosts: tuple[str, ...] = (),
) -> tuple[list[NormalizedJob], int]:
    """Return (live_jobs, dropped_count)."""
    to_check: list[NormalizedJob] = []
    skipped: list[NormalizedJob] = []
    for job in jobs:
        host = re.sub(r"^https?://", "", job.url).split("/")[0].lower()
        if any(h in host for h in skip_hosts):
            skipped.append(job)
            continue
        to_check.append(job)

    live: list[NormalizedJob] = []
    dead = 0
    if not to_check:
        return skipped, 0

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futs = {pool.submit(url_looks_alive, j.url): j for j in to_check}
        for fut in as_completed(futs):
            job = futs[fut]
            try:
                ok = fut.result()
            except Exception:  # noqa: BLE001
                ok = False
            if ok:
                live.append(job)
            else:
                dead += 1

    logger.info("URL verify: %d live, %d dead (skipped-unchecked %d)", len(live), dead, len(skipped))
    return live + skipped, dead
