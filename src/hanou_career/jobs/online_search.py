"""Fresh online job search (Arbeitsagentur API) + manual URL inbox."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

import httpx

from hanou_career.config import DATA_DIR, get_settings
from hanou_career.jobs.normalize import from_mapping
from hanou_career.jobs.schema import NormalizedJob

logger = logging.getLogger(__name__)

API_BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs"
PUBLIC_API_KEY = "jobboerse-jobsuche"

# Queries tuned for Hanou: BE-eligible clinical / Geriatrie / Reha / Innere.
SEARCH_QUERIES: list[tuple[str, str | None]] = [
    ("Assistenzarzt Geriatrie", None),
    ("Assistenzarzt Geriatrie", "Niedersachsen"),
    ("Assistenzarzt Innere Medizin", None),
    ("Assistenzarzt Innere Medizin", "Niedersachsen"),
    ("Assistenzarzt Reha", None),
    ("Arzt geriatrische Rehabilitation", None),
    ("Assistenzarzt Orthopädie", None),
    ("Assistenzarzt Berufserlaubnis", None),
    ("Arzt Anerkennung Berufserlaubnis", None),
    ("Hospitation Arzt Geriatrie", None),
]


def _public_url(refnr: str) -> str:
    encoded = base64.b64encode(refnr.encode("utf-8")).decode("ascii")
    return f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{encoded}"


def _payload_to_job(refnr: str, payload: dict[str, Any]) -> NormalizedJob | None:
    title = payload.get("titel") or payload.get("beruf")
    if not title:
        return None
    ort = payload.get("arbeitsort") or {}
    city = ort.get("ort")
    bundesland = ort.get("region")
    employer = payload.get("arbeitgeber")
    posted = payload.get("aktuelleVeroeffentlichungsdatum") or payload.get("eintrittsdatum")
    posted_s = str(posted)[:10] if posted else None
    # Short synthetic description from available JSON fields
    bits = [
        title,
        employer or "",
        f"{city or ''} {bundesland or ''}".strip(),
        payload.get("beruf") or "",
    ]
    description = " | ".join(b for b in bits if b)
    return from_mapping(
        {
            "id": f"aa-{refnr}",
            "url": _public_url(refnr),
            "title": title,
            "employer": employer,
            "city": city,
            "bundesland": bundesland,
            "description": description,
            "source": "online:arbeitsagentur",
            "posted_date": posted_s,
            "raw": {"arbeitsagentur": payload},
        },
        default_source="online:arbeitsagentur",
    )


def search_arbeitsagentur(*, max_pages: int | None = None) -> list[NormalizedJob]:
    settings = get_settings()
    pages = max_pages if max_pages is not None else settings.hanou_online_max_pages
    seen: set[str] = set()
    jobs: list[NormalizedJob] = []
    headers = {"X-API-Key": PUBLIC_API_KEY, "Accept": "application/json"}
    try:
        with httpx.Client(timeout=30.0, headers=headers) as client:
            for was, wo in SEARCH_QUERIES:
                for page in range(1, pages + 1):
                    params: dict[str, str | int] = {"was": was, "page": page, "size": 50}
                    if wo:
                        params["wo"] = wo
                    try:
                        res = client.get(API_BASE, params=params)
                    except httpx.HTTPError as exc:
                        logger.warning("Arbeitsagentur request failed (%s): %s", was, exc)
                        break
                    if res.status_code != 200:
                        logger.info("Arbeitsagentur %s -> %s", was, res.status_code)
                        break
                    data = res.json()
                    postings = data.get("stellenangebote") or []
                    if not postings:
                        break
                    for p in postings:
                        refnr = p.get("refnr")
                        if not refnr or refnr in seen:
                            continue
                        # Keep physician-ish titles only
                        title = (p.get("titel") or p.get("beruf") or "").lower()
                        if not any(
                            k in title
                            for k in (
                                "arzt",
                                "ärzt",
                                "assistenz",
                                "hospitat",
                                "mediziner",
                            )
                        ):
                            continue
                        seen.add(refnr)
                        job = _payload_to_job(str(refnr), p)
                        if job:
                            jobs.append(job)
                    total = data.get("maxErgebnisse") or 0
                    if page * 50 >= total:
                        break
    except Exception as exc:  # noqa: BLE001
        logger.warning("Online search aborted: %s", exc)
    logger.info("Online search found %d jobs", len(jobs))
    return jobs


def load_manual_inbox() -> list[NormalizedJob]:
    path = DATA_DIR / "search_manual.jsonl"
    if not path.is_file():
        return []
    jobs: list[NormalizedJob] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("Skipping invalid JSONL line in %s", path)
            continue
        job = from_mapping(data, default_source="manual")
        if job:
            jobs.append(job)
    logger.info("Manual inbox: %d jobs", len(jobs))
    return jobs


def fetch_online_jobs() -> list[NormalizedJob]:
    return search_arbeitsagentur() + load_manual_inbox()
