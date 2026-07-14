"""Read job_postings from the sibling Hano Postgres database (or var/*.jsonl)."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import create_engine, text

from hanou_career.config import REPO_ROOT, get_settings
from hanou_career.jobs.normalize import from_mapping
from hanou_career.jobs.schema import NormalizedJob, job_id_from_url, job_id_from_url


logger = logging.getLogger(__name__)

HANO_VAR = REPO_ROOT.parent / "Hano" / "var"

# Prefer physician-relevant titles / geriatrics-reha tags.
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
    ORDER BY jp.last_seen_at DESC NULLS LAST
    LIMIT :limit
    """
)


def _row_to_job(row: dict[str, Any], *, id_prefix: str, source: str) -> NormalizedJob | None:
    posted = row.get("posted_date")
    if hasattr(posted, "isoformat"):
        posted_s = posted.isoformat()
    else:
        posted_s = str(posted)[:10] if posted else None
    raw_id = row.get("id")
    # Never embed raw URLs in ids — they create nested/broken filesystem paths.
    if raw_id is None or (isinstance(raw_id, str) and ("://" in raw_id or "/" in raw_id)):
        suffix = job_id_from_url(row["url"])
    else:
        suffix = raw_id
    data = {
        "id": f"{id_prefix}-{suffix}",
        "url": row["url"],
        "title": row["title"],
        "employer": row.get("employer"),
        "city": row.get("city"),
        "bundesland": row.get("bundesland"),
        "description": row.get("full_text") or row.get("description") or "",
        "specializations": list(row.get("specializations") or []),
        "source": source,
        "posted_date": posted_s,
        "raw": {"hano": row.get("id")},
    }
    return from_mapping(data, default_source=source)


def fetch_hano_jsonl(*, limit: int = 800) -> list[NormalizedJob]:
    """Fallback when Postgres is down: read sibling Hano var/*.jsonl scrape dumps."""
    if not HANO_VAR.is_dir():
        return []
    jobs: list[NormalizedJob] = []
    for path in sorted(HANO_VAR.glob("*.jsonl")):
        name = path.name.lower()
        if "clinic" in name:
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if len(jobs) >= limit:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not row.get("url") or not row.get("title"):
                    continue
                title = (row.get("title") or "").lower()
                if not any(k in title for k in ("arzt", "ärzt", "assistenz", "hospitat")):
                    specs = " ".join(row.get("specializations") or []).lower()
                    if "geriatr" not in specs and "reha" not in specs:
                        continue
                job = _row_to_job(
                    row,
                    id_prefix=f"jsonl-{path.stem}",
                    source=f"hano-jsonl:{path.stem}",
                )
                if job:
                    jobs.append(job)
        except OSError as exc:
            logger.warning("Could not read %s: %s", path, exc)
        if len(jobs) >= limit:
            break
    logger.info("Loaded %d jobs from Hano var/*.jsonl", len(jobs))
    return jobs[:limit]


def fetch_hano_jobs(*, limit: int = 800) -> list[NormalizedJob]:
    settings = get_settings()
    try:
        engine = create_engine(settings.hano_database_url, pool_pre_ping=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not create Hano DB engine: %s", exc)
        return fetch_hano_jsonl(limit=limit)

    rows: list[dict[str, Any]] = []
    try:
        with engine.connect() as conn:
            result = conn.execute(SQL, {"limit": limit})
            for row in result.mappings():
                rows.append(dict(row))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Hano DB query failed (is Postgres up?): %s — trying JSONL", exc)
        try:
            engine.dispose()
        except Exception:  # noqa: BLE001
            pass
        return fetch_hano_jsonl(limit=limit)

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
    if not jobs:
        return fetch_hano_jsonl(limit=limit)
    return jobs
