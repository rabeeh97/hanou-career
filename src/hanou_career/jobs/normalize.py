"""Detect Approbation / Berufserlaubnis signals and light specialization tags."""

from __future__ import annotations

import re
from typing import Any

from hanou_career.jobs.schema import NormalizedJob, job_id_from_url

APPROBATION_ONLY = re.compile(
    r"(approbation\s+(zwingend|erforderlich|voraussetzung)|"
    r"volle\s+approbation|"
    r"nur\s+mit\s+approbation|"
    r"approbation\s+als\s+arzt\s+zwingend)",
    re.I,
)
APPROBATION_MENTION = re.compile(r"approbation", re.I)
BERUFSERLAUBNIS = re.compile(
    r"berufserlaubnis|beschr[äa]nkte\s+approbation|ohne\s+approbation|"
    r"anerkennung|gleichwertigkeit|approbation\s+oder\s+berufserlaubnis|"
    r"berufserlaubnis\s+(erw[üu]nscht|ausreichend|m[öo]glich)",
    re.I,
)

SPEC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "reha_geriatrie": ("geriatrie", "geriatr", "akutgeriatrie"),
    "reha": ("reha", "rehabilitation", "rehabilitat"),
    "innere": ("innere medizin", "internist", "innere"),
    "orthopaedie": ("orthopäd", "unfallchir", "bewegungsapparat"),
    "assistenzarzt": ("assistenzarzt", "assistenzärztin", "weiterbildungsassistent"),
}


def detect_licensing(text: str) -> tuple[bool | None, bool | None]:
    """Return (requires_approbation, accepts_berufserlaubnis)."""
    if not text:
        return None, None
    accepts_be = bool(BERUFSERLAUBNIS.search(text))
    requires_ap = bool(APPROBATION_ONLY.search(text))
    if not requires_ap and APPROBATION_MENTION.search(text) and not accepts_be:
        # Vague Approbation mention without BE alternative → soft risk, not hard block
        requires_ap = None
    return requires_ap, accepts_be if accepts_be else None


def tag_specializations(text: str) -> list[str]:
    low = text.lower()
    tags: list[str] = []
    for tag, keys in SPEC_KEYWORDS.items():
        if any(k in low for k in keys):
            tags.append(tag)
    return tags


def from_mapping(data: dict[str, Any], *, default_source: str = "manual") -> NormalizedJob | None:
    url = (data.get("url") or "").strip()
    title = (data.get("title") or "").strip()
    if not url or not title:
        return None
    if data.get("active") is False:
        return None
    description = data.get("description") or data.get("full_text") or ""
    blob = f"{title} {description} {data.get('employer') or ''}"
    req_ap, acc_be = detect_licensing(blob)
    specs = list(data.get("specializations") or []) or tag_specializations(blob)
    jid = data.get("id") or job_id_from_url(url)
    location = data.get("location")
    city = data.get("city")
    bundesland = data.get("bundesland")
    if not location:
        bits = [b for b in (city, bundesland) if b]
        location = ", ".join(bits) if bits else None
    return NormalizedJob(
        id=str(jid),
        title=title,
        employer=data.get("employer"),
        location=location,
        city=city,
        bundesland=bundesland,
        url=url,
        description=description or None,
        specializations=specs,
        source=str(data.get("source") or default_source),
        posted_date=data.get("posted_date"),
        requires_approbation=req_ap if data.get("requires_approbation") is None else data["requires_approbation"],
        accepts_berufserlaubnis=acc_be if data.get("accepts_berufserlaubnis") is None else data["accepts_berufserlaubnis"],
        raw=dict(data.get("raw") or data),
    )


def merge_jobs(jobs: list[NormalizedJob]) -> list[NormalizedJob]:
    by_url: dict[str, NormalizedJob] = {}
    for job in jobs:
        key = job.url.rstrip("/")
        existing = by_url.get(key)
        if existing is None:
            by_url[key] = job
            continue
        # Prefer richer description
        if (job.description or "") and len(job.description or "") > len(existing.description or ""):
            by_url[key] = job.model_copy(
                update={
                    "specializations": sorted(set(existing.specializations + job.specializations)),
                    "source": f"{existing.source}+{job.source}",
                }
            )
        else:
            specs = sorted(set(existing.specializations + job.specializations))
            by_url[key] = existing.model_copy(update={"specializations": specs})
    return list(by_url.values())
