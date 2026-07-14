"""Normalized job schema shared across ingest / rank / tailor / report."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from pydantic import BaseModel, Field


def slugify(text: str, *, max_len: int = 60) -> str:
    s = text.lower().strip()
    s = re.sub(r"[äÄ]", "ae", s)
    s = re.sub(r"[öÖ]", "oe", s)
    s = re.sub(r"[üÜ]", "ue", s)
    s = re.sub(r"ß", "ss", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return (s[:max_len] or "job").rstrip("-")


def job_id_from_url(url: str) -> str:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    return digest


class NormalizedJob(BaseModel):
    id: str
    title: str
    employer: str | None = None
    location: str | None = None
    city: str | None = None
    bundesland: str | None = None
    url: str
    description: str | None = None
    specializations: list[str] = Field(default_factory=list)
    source: str = "unknown"
    posted_date: str | None = None
    requires_approbation: bool | None = None
    accepts_berufserlaubnis: bool | None = None
    raw: dict[str, Any] = Field(default_factory=dict)

    @property
    def slug(self) -> str:
        base = slugify(f"{self.employer or 'klinik'}-{self.title}")
        # Sanitize id too — raw URLs / prefixes must never create nested paths.
        return f"{base}-{slugify(self.id, max_len=40)}"

    def text_blob(self) -> str:
        parts = [
            self.title,
            self.employer or "",
            self.location or "",
            self.city or "",
            self.bundesland or "",
            self.description or "",
            " ".join(self.specializations),
        ]
        return " ".join(p for p in parts if p).lower()


class RankedJob(BaseModel):
    job: NormalizedJob
    score: int
    rationale: str
    matched: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    eligibility: str = "unknown"  # eligible | risky | blocked
