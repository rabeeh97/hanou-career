"""Unit tests for ranking and CV render."""

from __future__ import annotations

from pathlib import Path

from hanou_career.cv.render_pdf import render_cv_pdf
from hanou_career.cv.tailor import analyze_gaps, tailor_cv
from hanou_career.jobs.normalize import from_mapping
from hanou_career.jobs.rank import rank_jobs
from hanou_career.jobs.schema import RankedJob


def test_rank_orders_by_score_descending() -> None:
    candidate = {
        "skills": ["Geriatrie"],
        "specializations_tokens": ["geriatrie", "reha"],
        "target_roles": ["Assistenzarzt Geriatrie"],
        "preferred_regions": ["Niedersachsen"],
        "licensing": {"approbation": False, "berufserlaubnis": True},
    }
    low = from_mapping(
        {
            "url": "https://example.test/low",
            "title": "Assistenzarzt Innere Medizin",
            "city": "Hannover",
            "bundesland": "Niedersachsen",
            "description": "Assistenzarzt Innere",
            "source": "manual",
            "posted_date": "2026-01-01",
        }
    )
    high = from_mapping(
        {
            "url": "https://example.test/high",
            "title": "Klinik-Ziel (Klinikradar): Rehaklinik Harz",
            "city": "Bad Harzburg",
            "bundesland": "Niedersachsen",
            "description": "Geriatrie Reha Berufserlaubnis Assistenzarzt",
            "source": "hano-jsonl:klinikradar",
            "posted_date": "2026-01-02",
        }
    )
    mid = from_mapping(
        {
            "url": "https://example.test/mid",
            "title": "Assistenzarzt Geriatrie Reha",
            "city": "Goslar",
            "bundesland": "Niedersachsen",
            "description": "Geriatrie Reha Berufserlaubnis Sonographie Visite",
            "source": "manual",
            "posted_date": "2026-01-03",
        }
    )
    ranked = rank_jobs([low, high, mid], candidate=candidate, top_n=10)
    scores = [r.score for r in ranked]
    assert scores == sorted(scores, reverse=True)
    assert ranked[0].score >= ranked[-1].score


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
    nrw = from_mapping(
        {
            "url": "https://example.test/nrw",
            "title": "Assistenzarzt Geriatrie",
            "employer": "Klinik NRW",
            "city": "Köln",
            "bundesland": "Nordrhein-Westfalen",
            "description": "Berufserlaubnis erwünscht. Geriatrie.",
        }
    )
    bad = from_mapping(
        {
            "url": "https://example.test/bad",
            "title": "Chefarzt Chirurgie",
            "employer": "Uni",
            "city": "Hannover",
            "bundesland": "Niedersachsen",
            "description": "Approbation zwingend erforderlich. Keine Berufserlaubnis.",
        }
    )
    assert good and nrw and bad
    ranked = rank_jobs([good, nrw, bad], candidate=candidate, top_n=5)
    assert all(r.job.url != "https://example.test/nrw" for r in ranked)
    assert ranked[0].job.title.startswith("Assistenzarzt")
    assert ranked[0].score > 50


def test_render_and_tailor(tmp_path: Path) -> None:
    master = {
        "headline": "Arzt",
        "summary": "Summary",
        "contact": {
            "name": "Mohammad Fares Hanou",
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
            "city": "Goslar",
            "bundesland": "Niedersachsen",
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


def test_blocks_oberarzt_keeps_assistenz() -> None:
    candidate = {
        "skills": ["Geriatrie"],
        "specializations_tokens": ["geriatrie"],
        "target_roles": ["Assistenzarzt Geriatrie"],
        "preferred_regions": ["Niedersachsen"],
    }
    aa = from_mapping(
        {
            "url": "https://example.test/aa",
            "title": "Assistenzarzt Geriatrie",
            "city": "Bad Harzburg",
            "bundesland": "Niedersachsen",
            "description": "Berufserlaubnis erwünscht Geriatrie Reha",
        }
    )
    oa = from_mapping(
        {
            "url": "https://example.test/oa",
            "title": "Oberarzt Geriatrie",
            "city": "Hannover",
            "bundesland": "Niedersachsen",
            "description": "Geriatrie Reha",
        }
    )
    fa = from_mapping(
        {
            "url": "https://example.test/fa",
            "title": "Facharzt für Innere Medizin",
            "city": "Göttingen",
            "bundesland": "Niedersachsen",
            "description": "Innere Medizin",
        }
    )
    ranked = rank_jobs([aa, oa, fa], candidate=candidate, top_n=10)
    titles = [r.job.title for r in ranked]
    assert any("Assistenzarzt" in t for t in titles)
    assert all("Oberarzt" not in t for t in titles)
    assert all(not t.startswith("Facharzt") for t in titles)
    scores = [r.score for r in ranked]
    assert scores == sorted(scores, reverse=True)
