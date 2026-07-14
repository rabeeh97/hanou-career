"""Load master CV YAML and write master PDF."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from hanou_career.config import DATA_DIR, OUTPUT_DIR
from hanou_career.cv.render_pdf import render_cv_pdf


def load_master_cv() -> dict[str, Any]:
    path = DATA_DIR / "master_cv.yaml"
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("master_cv.yaml must be a mapping")
    return data


def load_candidate() -> dict[str, Any]:
    path = DATA_DIR / "candidate.yaml"
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("candidate.yaml must be a mapping")
    return data


def build_master_pdf(*, out: Path | None = None) -> Path:
    cv = load_master_cv()
    out_path = out or (OUTPUT_DIR / "master_cv.pdf")
    return render_cv_pdf(cv, out_path)
