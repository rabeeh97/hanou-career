"""Fresh live scrapers for clinic/ATS boards (avoids dead Arbeitsagentur ghosts)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import urljoin

import httpx

from hanou_career.jobs.geo import NI_CITIES, is_niedersachsen
from hanou_career.jobs.normalize import from_mapping
from hanou_career.jobs.schema import NormalizedJob, job_id_from_url

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json",
}

JOB_HREF_RE = re.compile(r"job/\d+/[A-Za-z0-9\-\._%]+")
PHYSICIAN_RE = re.compile(
    r"arzt|ärztin|assistenz|hospitat|mediziner|stationsarzt", re.I
)

def _is_junior_title(title: str) -> bool:
    t = (title or "").lower()
    if any(k in t for k in ("oberarzt", "oberärztin", "chefarzt", "chefärztin")):
        return "assistenz" in t
    if ("facharzt" in t or "fachärztin" in t) and "assistenz" not in t:
        if "arzt in weiterbildung" not in t and "hospitat" not in t:
            return False
    return bool(PHYSICIAN_RE.search(t))

AGAPLESION_LISTING = "https://agaplesion-jobs.softgarden.io/"
MEDICLIN_JSON = "https://www.mediclin-karriere.de/jobs/jobs.json"
SCHOEN_LISTING = "https://jobs.schoen-klinik.de/stellenangebote.html"
MEDIAN_LISTING = "https://karriere.median-kliniken.de/de/jobs/"


def _ni_blob(text: str) -> bool:
    low = text.lower()
    if "niedersachsen" in low:
        return True
    for city in NI_CITIES:
        if city and city in low:
            return True
    return False


def _extract_jsonld_job(html: str) -> dict[str, Any] | None:
    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.I | re.S,
    ):
        raw = m.group(1).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            typ = item.get("@type")
            if typ == "JobPosting" or (isinstance(typ, list) and "JobPosting" in typ):
                return item
    return None


def _job_from_jsonld(url: str, data: dict[str, Any], *, source: str) -> NormalizedJob | None:
    title = data.get("title") or data.get("name")
    if not title or not PHYSICIAN_RE.search(str(title)):
        return None
    employer = None
    org = data.get("hiringOrganization")
    if isinstance(org, dict):
        employer = org.get("name")
    city = bundesland = None
    loc = data.get("jobLocation")
    if isinstance(loc, list) and loc:
        loc = loc[0]
    if isinstance(loc, dict):
        addr = loc.get("address") or {}
        if isinstance(addr, dict):
            city = addr.get("addressLocality")
            bundesland = addr.get("addressRegion")
            if not bundesland:
                country_parts = str(addr.get("addressRegion") or "") + " " + str(
                    addr.get("addressLocality") or ""
                )
                if _ni_blob(country_parts + " " + str(addr)):
                    bundesland = "Niedersachsen"
    description = data.get("description") or ""
    if isinstance(description, str):
        description = re.sub(r"<[^>]+>", " ", description)
        description = re.sub(r"\s+", " ", description).strip()[:4000]
    posted = data.get("datePosted")
    posted_s = str(posted)[:10] if posted else None
    job = from_mapping(
        {
            "id": f"live-{job_id_from_url(url)}",
            "url": url,
            "title": str(title),
            "employer": employer,
            "city": city,
            "bundesland": bundesland or ("Niedersachsen" if _ni_blob(f"{city} {description}") else None),
            "description": description,
            "source": source,
            "posted_date": posted_s,
            "raw": {"jsonld": True},
        },
        default_source=source,
    )
    return job


def fetch_agaplesion_ni(*, max_details: int = 150) -> list[NormalizedJob]:
    jobs: list[NormalizedJob] = []
    try:
        with httpx.Client(timeout=45.0, follow_redirects=True, headers=HEADERS) as client:
            listing = client.get(AGAPLESION_LISTING)
            listing.raise_for_status()
            hrefs = []
            seen: set[str] = set()
            for m in JOB_HREF_RE.finditer(listing.text):
                full = urljoin(AGAPLESION_LISTING, m.group(0))
                key = full.split("?", 1)[0]
                if key in seen:
                    continue
                seen.add(key)
                # Prefer physician-sounding slugs first
                slug = key.lower()
                if PHYSICIAN_RE.search(slug):
                    hrefs.insert(0, full)
                else:
                    hrefs.append(full)

            checked = 0
            for url in hrefs:
                if len(jobs) >= max_details or checked >= max_details * 3:
                    break
                checked += 1
                try:
                    res = client.get(url)
                except httpx.HTTPError:
                    continue
                if res.status_code >= 400:
                    continue
                data = _extract_jsonld_job(res.text)
                if not data:
                    continue
                job = _job_from_jsonld(url, data, source="live:agaplesion")
                if not job or not _is_junior_title(job.title):
                    continue
                # Location filter: NI city / region / description
                if not is_niedersachsen(job) and not _ni_blob(job.text_blob()):
                    continue
                jobs.append(job)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Agaplesion live scrape failed: %s", exc)
    logger.info("Agaplesion live NI physician jobs: %d", len(jobs))
    return jobs


def fetch_mediclin_ni() -> list[NormalizedJob]:
    jobs: list[NormalizedJob] = []
    try:
        with httpx.Client(timeout=30.0, headers=HEADERS) as client:
            res = client.get(MEDICLIN_JSON)
            res.raise_for_status()
            payload = res.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Mediclin jobs.json failed: %s", exc)
        return []

    items = payload if isinstance(payload, list) else payload.get("jobs") or payload.get("items") or []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("name") or ""
        if not PHYSICIAN_RE.search(str(title)):
            continue
        url = item.get("url") or item.get("link") or item.get("absolute_url")
        if not url:
            continue
        if url.startswith("/"):
            url = urljoin("https://www.mediclin-karriere.de/", url)
        city = item.get("city") or item.get("location") or item.get("ort")
        bundesland = item.get("bundesland") or item.get("region") or item.get("state")
        desc = item.get("description") or item.get("content") or ""
        job = from_mapping(
            {
                "id": f"live-mediclin-{job_id_from_url(str(url))}",
                "url": str(url),
                "title": str(title),
                "employer": item.get("employer") or item.get("company") or "MediClin",
                "city": city if isinstance(city, str) else None,
                "bundesland": bundesland if isinstance(bundesland, str) else None,
                "description": str(desc)[:4000],
                "source": "live:mediclin",
                "posted_date": str(item.get("date") or item.get("posted") or "")[:10] or None,
                "raw": item,
            },
            default_source="live:mediclin",
        )
        if job and (is_niedersachsen(job) or _ni_blob(job.text_blob())):
            jobs.append(job)
    logger.info("Mediclin live NI physician jobs: %d", len(jobs))
    return jobs


def _listing_physician_links(listing_url: str, href_substr: str) -> list[str]:
    try:
        with httpx.Client(timeout=40.0, follow_redirects=True, headers=HEADERS) as client:
            res = client.get(listing_url)
            res.raise_for_status()
            html = res.text
    except Exception as exc:  # noqa: BLE001
        logger.warning("Listing fetch failed (%s): %s", listing_url, exc)
        return []
    urls: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r'href=["\']([^"\']+)["\']', html, re.I):
        href = m.group(1)
        if href_substr not in href.lower():
            continue
        full = urljoin(listing_url, href)
        key = full.split("#", 1)[0]
        if key in seen:
            continue
        seen.add(key)
        if PHYSICIAN_RE.search(full) or PHYSICIAN_RE.search(html[max(0, m.start() - 80) : m.end() + 80]):
            urls.append(full)
        elif "stelle" in href.lower() or "job" in href.lower():
            urls.append(full)
    return urls


def fetch_jsonld_board(
    listing_url: str,
    *,
    source: str,
    href_substr: str,
    max_details: int = 40,
) -> list[NormalizedJob]:
    jobs: list[NormalizedJob] = []
    links = _listing_physician_links(listing_url, href_substr)
    try:
        with httpx.Client(timeout=40.0, follow_redirects=True, headers=HEADERS) as client:
            for url in links[: max_details * 2]:
                if len(jobs) >= max_details:
                    break
                try:
                    res = client.get(url)
                except httpx.HTTPError:
                    continue
                if res.status_code >= 400:
                    continue
                data = _extract_jsonld_job(res.text)
                if not data:
                    # fallback: title from <title>
                    tm = re.search(r"<title>([^<]+)</title>", res.text, re.I)
                    title = tm.group(1).strip() if tm else None
                    if not title or not PHYSICIAN_RE.search(title):
                        continue
                    job = from_mapping(
                        {
                            "id": f"live-{job_id_from_url(url)}",
                            "url": url,
                            "title": title.split("|")[0].split("-")[0].strip(),
                            "description": "",
                            "source": source,
                        },
                        default_source=source,
                    )
                else:
                    job = _job_from_jsonld(url, data, source=source)
                if job and (is_niedersachsen(job) or _ni_blob(job.text_blob()) or True):
                    # boards may omit region — keep physician roles; NI filter later soft
                    jobs.append(job)
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s board scrape failed: %s", source, exc)
    logger.info("%s live physician jobs: %d", source, len(jobs))
    return jobs


def fetch_live_clinic_jobs() -> list[NormalizedJob]:
    """Pull current openings from clinic ATS boards."""
    jobs: list[NormalizedJob] = []
    jobs.extend(fetch_agaplesion_ni())
    jobs.extend(fetch_mediclin_ni())
    jobs.extend(
        fetch_jsonld_board(
            SCHOEN_LISTING,
            source="live:schoen",
            href_substr="stelle",
            max_details=30,
        )
    )
    jobs.extend(
        fetch_jsonld_board(
            MEDIAN_LISTING,
            source="live:median",
            href_substr="job",
            max_details=30,
        )
    )
    # Soft NI preference when bundesland missing: keep if city matched else drop non-NI
    scoped: list[NormalizedJob] = []
    for job in jobs:
        if is_niedersachsen(job) or _ni_blob(job.text_blob()):
            scoped.append(job)
        elif not job.bundesland and not job.city:
            # unknown geo — keep for verify+rank NI filter to drop
            scoped.append(job)
    logger.info("Live clinic boards total (pre-filter): %d", len(scoped))
    return scoped
