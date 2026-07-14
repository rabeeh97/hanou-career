"""Unit tests for ranking and CV render."""

from __future__ import annotations

from pathlib import Path

from hanou_career.cv.render_pdf import render_cv_pdf
from hanou_career.cv.tailor import analyze_gaps, tailor_cv
from hanou_career.jobs.normalize import from_mapping
from hanou_career.jobs.rank import rank_jobs
from hanou_career.jobs.schema import RankedJob


def test_rank_prefers_geriatrie_be() -> None:
    candidate = {
        "skills": ["Geriatrie", "Sonographie"],
        "specializations_tokens": ["geriatrie", "reha"],
        "target_roles": ["Assistenzarzt Geriatrie"],
        "preferred_regions": ["Niedersachsen"],
        "licensing": {"approbation": False, "berufserlaubnis": True},
    }
    good = from_mapping(
        {
            "url": "https://example.test/good",
            "title": "Assistenzarzt Geriatrie",
            "employer": "Rehaklinik Harz",
            "city": "Bad Harzburg",
            "bundesland": "Niedersachsen",
            "description": "Berufserlaubnis erwünscht. Visite, Anamnese, Sonographie.",
        }
    )
    bad = from_mapping(
        {
            "url": "https://example.test/bad",
            "title": "Chefarzt Chirurgie",
            "employer": "Uni",
            "city": "München",
            "description": "Approbation zwingend erforderlich. Keine Berufserlaubnis.",
        }
    )
    assert good and bad
    ranked = rank_jobs([good, bad], candidate=candidate, top_n=5)
    assert ranked[0].job.title.startswith("Assistenzarzt")
    assert ranked[0].score > 50


def test_render_and_tailor(tmp_path: Path) -> None:
    master = {
        "headline": "Arzt",
        "summary": "Summary",
        "contact": {
            "name": "Mohamad Fares Hanou",
            "email": "a@b.c",
            "phone": "+49",
            "address": "Bad Harzburg",
        },
        "sections": {
            "berufserfahrung": [
                {
                    "title": "Hospitant",
                    "employer": "Klinik",
                    "period": "2025–2026",
                    "bullets": ["Visite"],
                }
            ]
        },
    }
    pdf = render_cv_pdf(master, tmp_path / "master.pdf")
    assert pdf.is_file() and pdf.stat().st_size > 500

    job = from_mapping(
        {
            "url": "https://example.test/j",
            "title": "Assistenzarzt Geriatrie",
            "employer": "Testklinik",
            "description": "Geriatrie Reha Sonographie Berufserlaubnis",
        }
    )
    assert job
    ranked = RankedJob(
        job=job, score=80, rationale="fit", matched=["geriatrie"], eligibility="eligible"
    )
    tailored = tailor_cv(master, ranked)
    assert "Geriatrie" in tailored["headline"] or "geriatr" in tailored["headline"].lower()
    gaps = analyze_gaps(ranked, {"licensing": {"approbation": False}})
    assert gaps
