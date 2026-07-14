"""Read job_postings from the sibling Hano Postgres database (or var/*.jsonl)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

from hanou_career.config import REPO_ROOT, get_settings
from hanou_career.jobs.normalize import from_mapping
from hanou_career.jobs.schema import NormalizedJob, job_id_from_url

logger = logging.getLogger(__name__)

HANO_VAR = REPO_ROOT.parent / "Hano" / "var"

# Prefer physician-relevant titles / geriatrics-reha tags; Niedersachsen preferred when available.
SQL = text(
    """
    SELECT
      jp.id,
      jp.url,
      jp.title,
      jp.employer,
      jp.city,
      jp.bundesland,
      jp.full_text,
      jp.specializations,
      jp.posted_date,
      s.slug AS source_slug
    FROM job_postings jp
    JOIN sources s ON s.id = jp.source_id
    WHERE
      (
        jp.title ILIKE '%arzt%'
        OR jp.title ILIKE '%ärztin%'
        OR jp.title ILIKE '%assistenz%'
        OR jp.title ILIKE '%hospitat%'
        OR jp.full_text ILIKE '%assistenzarzt%'
        OR jp.full_text ILIKE '%berufserlaubnis%'
        OR 'reha_geriatrie' = ANY(jp.specializations)
        OR 'reha_orthopaedie' = ANY(jp.specializations)
        OR 'reha_neurologie' = ANY(jp.specializations)
      )
    ORDER BY
      CASE WHEN jp.bundesland ILIKE '%niedersachsen%' THEN 0 ELSE 1 END,
      jp.last_seen_at DESC NULLS LAST
    LIMIT :limit
    """
)

JOB_FILE_GLOBS = (
    "*-full.jsonl",
    "*-extract.jsonl",
    "career-page-jobs.jsonl",
    "arbeitsagentur*.jsonl",
)

SKIP_NAME_PARTS = ("clinic-career-pages",)


def _row_to_job(row: dict[str, Any], *, id_prefix: str, source: str) -> NormalizedJob | None:
    posted = row.get("posted_date")
    if hasattr(posted, "isoformat"):
        posted_s = posted.isoformat()
    else:
        posted_s = str(posted)[:10] if posted else None
    url = row.get("url") or row.get("raw_url")
    title = row.get("title") or row.get("name")
    if not url or not title:
        return None
    raw_id = row.get("id") or row.get("external_id")
    if raw_id is None or (isinstance(raw_id, str) and ("://" in raw_id or "/" in raw_id)):
        suffix = job_id_from_url(str(url))
    else:
        suffix = raw_id
    data = {
        "id": f"{id_prefix}-{suffix}",
        "url": str(url),
        "title": str(title),
        "employer": row.get("employer") or row.get("name"),
        "city": row.get("city"),
        "bundesland": row.get("bundesland"),
        "description": row.get("full_text") or row.get("description") or "",
        "specializations": list(row.get("specializations") or []),
        "source": source,
        "posted_date": posted_s,
        "raw": {"hano": row.get("id"), "plz": row.get("plz")},
    }
    return from_mapping(data, default_source=source)


def _is_physicianish(row: dict[str, Any]) -> bool:
    title = (row.get("title") or row.get("name") or "").lower()
    if any(k in title for k in ("arzt", "ärzt", "assistenz", "hospitat", "mediziner")):
        return True
    specs = " ".join(str(s) for s in (row.get("specializations") or [])).lower()
    return any(k in specs for k in ("geriatr", "reha", "innere", "orthop"))


def _iter_job_jsonl_paths() -> list[Path]:
    if not HANO_VAR.is_dir():
        return []
    found: dict[str, Path] = {}
    for pattern in JOB_FILE_GLOBS:
        for path in HANO_VAR.glob(pattern):
            name = path.name.lower()
            if any(s in name for s in SKIP_NAME_PARTS):
                continue
            if "clinic" in name and "career-page-jobs" not in name:
                continue
            # Prefer -full over -dry / duplicates by stem family
            key = path.stem.replace("-full", "").replace("-extract", "").replace("-dry", "")
            prev = found.get(key)
            if prev is None:
                found[key] = path
            elif "-full" in path.name and "-full" not in prev.name:
                found[key] = path
            elif "-extract" in path.name and "-dry" in prev.name:
                found[key] = path
    return sorted(found.values(), key=lambda p: p.name)


def fetch_klinikradar_ni_clinics() -> list[NormalizedJob]:
    """Turn Klinikradar NI clinics into discovery targets (career leads)."""
    paths = [
        HANO_VAR / "klinikradar-clinics-enriched.jsonl",
        HANO_VAR / "klinikradar-clinics.jsonl",
    ]
    jobs: list[NormalizedJob] = []
    seen: set[str] = set()
    for path in paths:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (row.get("bundesland") or "").lower() != "niedersachsen":
                continue
            url = row.get("website") or row.get("raw_url")
            name = row.get("name")
            if not url or not name or url in seen:
                continue
            seen.add(url)
            specs = list(row.get("specializations") or [])
            spec_txt = ", ".join(specs) if specs else "Reha / Klinik"
            desc = (
                f"Klinikradar-Klinik in Niedersachsen ({spec_txt}). "
                f"Adresse: {row.get('address') or row.get('city') or '—'}. "
                "Kein einzelnes Stellenangebot — Karriere-/Kontaktseite prüfen auf "
                "Assistenzarzt / Berufserlaubnis / Geriatrie-Reha."
            )
            job = from_mapping(
                {
                    "id": f"klinikradar-{row.get('external_id') or job_id_from_url(url)}",
                    "url": url,
                    "title": f"Klinik-Ziel (Klinikradar): {name}",
                    "employer": name,
                    "city": row.get("city"),
                    "bundesland": "Niedersachsen",
                    "description": desc,
                    "specializations": specs or ["reha_geriatrie"],
                    "source": "hano-jsonl:klinikradar",
                    "accepts_berufserlaubnis": True,
                    "raw": {"plz": row.get("plz"), "klinikradar": row.get("external_id")},
                },
                default_source="hano-jsonl:klinikradar",
            )
            if job:
                jobs.append(job)
        if jobs:
            break  # enriched first if present
    logger.info("Klinikradar NI clinics as leads: %d", len(jobs))
    return jobs


def fetch_hano_jsonl(*, limit: int | None = None) -> list[NormalizedJob]:
    """Read sibling Hano var/*.jsonl scrape dumps from many sources."""
    settings = get_settings()
    lim = limit if limit is not None else settings.hanou_jsonl_limit
    if not HANO_VAR.is_dir():
        return []
    jobs: list[NormalizedJob] = []
    per_source: dict[str, int] = {}
    for path in _iter_job_jsonl_paths():
        src_count = 0
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if len(jobs) >= lim:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not _is_physicianish(row) and "career-page" not in path.name:
                    continue
                # Skip obvious non-job marketing titles from career harvest
                title = (row.get("title") or "").lower()
                if title in {"gib dir gesundheit", "karriere", "jobs"}:
                    continue
                job = _row_to_job(
                    row,
                    id_prefix=f"jsonl-{path.stem}",
                    source=f"hano-jsonl:{path.stem}",
                )
                if job:
                    jobs.append(job)
                    src_count += 1
        except OSError as exc:
            logger.warning("Could not read %s: %s", path, exc)
        if src_count:
            per_source[path.name] = src_count
        if len(jobs) >= lim:
            break

    jobs.extend(fetch_klinikradar_ni_clinics())
    logger.info(
        "Loaded %d jobs from Hano var JSONL (%d files contributed)",
        len(jobs),
        len(per_source),
    )
    for name, count in sorted(per_source.items(), key=lambda x: -x[1])[:12]:
        logger.info("  · %s: %d", name, count)
    return jobs[: lim + 50]


def fetch_hano_jobs(*, limit: int | None = None) -> list[NormalizedJob]:
    settings = get_settings()
    lim = limit if limit is not None else settings.hanou_jsonl_limit
    try:
        engine = create_engine(settings.hano_database_url, pool_pre_ping=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not create Hano DB engine: %s", exc)
        return fetch_hano_jsonl(limit=lim)

    rows: list[dict[str, Any]] = []
    try:
        with engine.connect() as conn:
            result = conn.execute(SQL, {"limit": lim})
            for row in result.mappings():
                rows.append(dict(row))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Hano DB query failed (is Postgres up?): %s — trying JSONL", exc)
        try:
            engine.dispose()
        except Exception:  # noqa: BLE001
            pass
        return fetch_hano_jsonl(limit=lim)

    try:
        engine.dispose()
    except Exception:  # noqa: BLE001
        pass

    jobs: list[NormalizedJob] = []
    for row in rows:
        job = _row_to_job(
            row,
            id_prefix="hano",
            source=f"hano:{row.get('source_slug') or 'db'}",
        )
        if job:
            jobs.append(job)
    logger.info("Loaded %d jobs from Hano DB", len(jobs))
    # Always merge JSONL + klinikradar for broader coverage
    jsonl_jobs = fetch_hano_jsonl(limit=lim)
    from hanou_career.jobs.normalize import merge_jobs

    merged = merge_jobs(jobs + jsonl_jobs)
    logger.info("Merged DB+JSONL → %d unique jobs", len(merged))
    return merged
