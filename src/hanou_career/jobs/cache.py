"""Job cache helpers."""

from __future__ import annotations

import json
from pathlib import Path

from hanou_career.jobs.schema import NormalizedJob, RankedJob


def save_jobs(path: Path, jobs: list[NormalizedJob]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [j.model_dump() for j in jobs]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_jobs(path: Path) -> list[NormalizedJob]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [NormalizedJob.model_validate(item) for item in data]


def save_ranked(path: Path, ranked: list[RankedJob]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [r.model_dump() for r in ranked]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_ranked(path: Path) -> list[RankedJob]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [RankedJob.model_validate(item) for item in data]
