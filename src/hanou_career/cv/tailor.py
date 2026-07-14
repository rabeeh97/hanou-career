"""Per-job CV tailoring and gap analysis (honest, no invented credentials)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from hanou_career.config import OUTPUT_DIR
from hanou_career.cv.master import load_master_cv
from hanou_career.cv.render_pdf import render_cv_pdf
from hanou_career.jobs.schema import RankedJob

FOCUS_MAP: list[tuple[tuple[str, ...], str, list[str]]] = [
    (
        ("geriatr", "akutgeriatrie"),
        "Arzt mit Berufserlaubnis | Schwerpunkt Geriatrie & geriatrische Rehabilitation",
        [
            "Selbstständige Anamneseerhebung und körperliche Untersuchung unter Supervision in der Geriatrie.",
            "Regelmäßige fachärztliche Visiten; multimorbide Patienten in der geriatrischen Reha.",
            "Grundkenntnisse Abdomen-, Herz- und Venensonographie; Aufnahme–Behandlung–Entlassung.",
        ],
    ),
    (
        ("reha", "rehabilitation"),
        "Arzt mit Berufserlaubnis | geriatrische & medizinische Rehabilitation",
        [
            "Hospitation in Fachklinik für Geriatrische Rehabilitation (131 Betten), Bad Harzburg.",
            "Mitwirkung im gesamten Reha-Prozess: Aufnahme, Behandlung, Entlassung.",
            "Interdisziplinäre Zusammenarbeit mit Pflege, Therapie und Sozialdienst.",
        ],
    ),
    (
        ("innere", "internist", "kardiolog"),
        "Arzt mit Berufserlaubnis | Innere Medizin & geriatrische Komorbidität",
        [
            "Rotationen Innere Medizin (Kardiologie, Gastroenterologie, Nephrologie u. a.) als Assistenzarzt.",
            "Geriatrische Patienten mit kardiologischen und multimorbiden Verläufen.",
            "Grundkenntnisse Herz- und Abdomen-Sonographie; klinische Dokumentation.",
        ],
    ),
    (
        ("orthopäd", "unfall", "bewegungsapparat"),
        "Arzt mit Berufserlaubnis | Bewegungsapparat & geriatrische Orthoreha",
        [
            "Assistenzarzt Erfahrung Erkrankungen des Bewegungsapparates (Syrien).",
            "Geriatrische Reha mit chirurgisch-orthopädischen Patientenanteilen.",
            "Visite, Untersuchung und Teamarbeit in der Rehabilitation.",
        ],
    ),
]


def _pick_focus(blob: str) -> tuple[str, list[str]]:
    for keys, headline, bullets in FOCUS_MAP:
        if any(k in blob for k in keys):
            return headline, bullets
    return (
        "Arzt mit Berufserlaubnis | klinische Tätigkeit (Geriatrie / Reha / Innere)",
        [
            "Berufserlaubnis vorhanden; Fachsprachprüfung bestanden; Anerkennung läuft.",
            "Sechs Monate Hospitation Geriatrie / Reha in Bad Harzburg.",
            "Assistenzarzt-Erfahrung und interdisziplinäre Teamarbeit.",
        ],
    )


def tailor_cv(master: dict[str, Any], ranked: RankedJob) -> dict[str, Any]:
    cv = copy.deepcopy(master)
    job = ranked.job
    blob = job.text_blob()
    headline, focus_bullets = _pick_focus(blob)
    cv["headline"] = headline

    employer = job.employer or "der Klinik"
    title = job.title
    cv["summary"] = (
        f"Bewerbung als {title} bei {employer}. "
        "Humanmediziner mit Berufserlaubnis und bestandener Fachsprachprüfung; "
        "Hospitation in geriatrischer Rehabilitation (Herzog-Julius-Klinik, 11/2025–04/2026) "
        "mit Anamnese/Untersuchung unter Supervision, Visiten und Sono-Grundkenntnissen. "
        "Anerkennung in Deutschland in Bearbeitung; keine Approbation. "
        "Motiviert für klinische Assistenzarzt-Tätigkeit mit Berufserlaubnis."
    )

    sections = cv.get("sections") or {}
    hosp = (sections.get("berufserfahrung") or [None])[0]
    if isinstance(hosp, dict):
        # Prepend focus bullets (unique), keep Zeugnis depth
        existing = list(hosp.get("bullets") or [])
        merged = focus_bullets + [b for b in existing if b not in focus_bullets]
        hosp["bullets"] = merged[:7]

    # Reorder kenntnisse bullets to mirror job keywords
    kennt = (sections.get("kenntnisse") or [None])[0]
    if isinstance(kennt, dict):
        bullets = list(kennt.get("bullets") or [])
        prioritized: list[str] = []
        for b in bullets:
            bl = b.lower()
            if any(k in blob for k in ("geriatr", "reha")) and "geriatr" in bl:
                prioritized.insert(0, b)
            elif "sono" in blob and "sono" in bl:
                prioritized.insert(0, b)
            else:
                prioritized.append(b)
        kennt["bullets"] = list(dict.fromkeys(prioritized))

    return cv


def analyze_gaps(ranked: RankedJob, candidate: dict[str, Any]) -> list[str]:
    job = ranked.job
    blob = job.text_blob()
    gaps: list[str] = []

    if job.requires_approbation or ("approbation" in blob and not job.accepts_berufserlaubnis):
        gaps.append(
            "Approbation fehlt — im Anschreiben Berufserlaubnis + laufende Anerkennung klar nennen; "
            "nachfragen, ob BE ausreicht."
        )
    else:
        gaps.append(
            "Im Anschreiben Berufserlaubnis (Restlaufzeit ~2 Jahre) und FSP früh erwähnen."
        )

    if "facharzt" in blob and "assistenz" not in job.title.lower():
        gaps.append(
            "Anzeige wirkt facharztnah — prüfen, ob Assistenz-/Weiterbildungsstelle gemeint ist; "
            "sonst eher nicht bewerben."
        )

    if any(k in blob for k in ("sonographie", "ultraschall", "echo")):
        gaps.append(
            "Sono wird genannt: Abdomen-/Herz-/Venensonographie aus dem Zeugnis prominent halten "
            "(Grundkenntnisse, nicht Facharzttiefe vortäuschen)."
        )

    if any(k in blob for k in ("englisch", "english")):
        gaps.append("Englisch B2 reicht ggf. — im CV-Block belassen; DE C1 + FSP stärker betonen.")

    if any(k in blob for k in ("führerschein", "fuhrerschein", "fahrzeug")):
        gaps.append(
            "Falls Führerschein gefordert: Status in Profil/Anschreiben ergänzen (aktuell nicht im Master-CV)."
        )

    if "hospitat" in blob:
        gaps.append(
            "Weitere Hospitation möglich — Zeugnis von Dr. Willjes als Anlage beilegen."
        )

    if ranked.eligibility == "risky":
        gaps.append(
            "Eligibility risky: vor Bewerbung telefonisch/per Mail klären, ob Berufserlaubnis akzeptiert wird."
        )

    # Always useful structural tips
    gaps.append(
        f"Stellenbezeichnung „{job.title}“ in Überschrift/Zusammenfassung der Bewerbung wörtlich aufnehmen."
    )
    if job.employer:
        gaps.append(f"Motivationssatz mit Bezug auf {job.employer} und deren Schwerpunkt formulieren.")

    licensing = candidate.get("licensing") or {}
    if not licensing.get("approbation"):
        gaps.append(
            "Keine Approbation erfinden; nicht als „approbierter Arzt“ bezeichnen."
        )

    return gaps


def write_tailored_artifacts(
    ranked: RankedJob,
    *,
    candidate: dict[str, Any],
    master: dict[str, Any] | None = None,
    output_root: Path | None = None,
) -> Path:
    master = master or load_master_cv()
    root = output_root or OUTPUT_DIR
    job_dir = root / "jobs" / ranked.job.slug
    job_dir.mkdir(parents=True, exist_ok=True)

    tailored = tailor_cv(master, ranked)
    render_cv_pdf(tailored, job_dir / "cv.pdf")

    gaps = analyze_gaps(ranked, candidate)
    gaps_md = [
        f"# CV-Anpassungen für: {ranked.job.title}",
        "",
        f"**Arbeitgeber:** {ranked.job.employer or '—'}  ",
        f"**Ort:** {ranked.job.location or '—'}  ",
        f"**Score:** {ranked.score}/100 · **Eligibility:** {ranked.eligibility}",
        "",
        f"**Fit:** {ranked.rationale}",
        "",
        "## Empfohlene Änderungen",
        "",
    ]
    for i, g in enumerate(gaps, 1):
        gaps_md.append(f"{i}. {g}")
    gaps_md.extend(
        [
            "",
            "## Links",
            "",
            f"- Stellenanzeige: {ranked.job.url}",
            f"- Maßgeschneiderter CV: [cv.pdf](cv.pdf)",
            f"- Master-CV: [../../master_cv.pdf](../../master_cv.pdf)",
            "",
        ]
    )
    (job_dir / "gaps.md").write_text("\n".join(gaps_md), encoding="utf-8")

    payload = {
        "score": ranked.score,
        "eligibility": ranked.eligibility,
        "rationale": ranked.rationale,
        "matched": ranked.matched,
        "risks": ranked.risks,
        "gaps": gaps,
        "job": ranked.job.model_dump(),
    }
    (job_dir / "job.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return job_dir
