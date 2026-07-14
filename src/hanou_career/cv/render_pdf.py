"""Render a German Lebenslauf PDF from structured CV data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

ACCENT = HexColor("#1a4d4a")
MUTED = HexColor("#4a5560")
RULE = HexColor("#c5d0ce")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "name": ParagraphStyle(
            "Name",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=18,
            textColor=ACCENT,
            spaceAfter=2 * mm,
            leading=22,
        ),
        "headline": ParagraphStyle(
            "Headline",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            textColor=MUTED,
            spaceAfter=2 * mm,
            leading=13,
        ),
        "contact": ParagraphStyle(
            "Contact",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            textColor=MUTED,
            spaceAfter=3 * mm,
            leading=11,
        ),
        "summary": ParagraphStyle(
            "Summary",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=HexColor("#222"),
            spaceAfter=4 * mm,
            leading=12,
        ),
        "section": ParagraphStyle(
            "Section",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=ACCENT,
            spaceBefore=3 * mm,
            spaceAfter=1.5 * mm,
            leading=12,
        ),
        "job_title": ParagraphStyle(
            "JobTitle",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            textColor=HexColor("#1a1a1a"),
            spaceBefore=2 * mm,
            leading=12,
        ),
        "job_meta": ParagraphStyle(
            "JobMeta",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            textColor=MUTED,
            spaceAfter=1 * mm,
            leading=11,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            textColor=HexColor("#222"),
            leftIndent=4 * mm,
            spaceAfter=0.6 * mm,
            leading=11,
        ),
    }


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


SECTION_LABELS = {
    "berufserfahrung": "Berufserfahrung",
    "ausbildung": "Ausbildung",
    "qualifikationen_lizenzen": "Qualifikationen & Lizenzen",
    "sprachen": "Sprachen",
    "kenntnisse": "Kenntnisse",
}


def render_cv_pdf(cv: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    styles = _styles()
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=cv.get("contact", {}).get("name", "Lebenslauf"),
    )
    story: list[Any] = []
    contact = cv.get("contact") or {}
    name = contact.get("name") or "Lebenslauf"
    story.append(Paragraph(_esc(name), styles["name"]))
    if cv.get("headline"):
        story.append(Paragraph(_esc(cv["headline"]), styles["headline"]))
    contact_bits = [
        contact.get("address"),
        contact.get("email"),
        contact.get("phone"),
        f"Geboren: {contact['birth']}" if contact.get("birth") else None,
    ]
    story.append(
        Paragraph(" · ".join(_esc(b) for b in contact_bits if b), styles["contact"])
    )
    story.append(HRFlowable(width="100%", thickness=0.8, color=RULE, spaceAfter=3 * mm))
    if cv.get("summary"):
        story.append(Paragraph(_esc(cv["summary"].strip()), styles["summary"]))

    sections = cv.get("sections") or {}
    for key, label in SECTION_LABELS.items():
        entries = sections.get(key) or []
        if not entries:
            continue
        story.append(Paragraph(label.upper(), styles["section"]))
        story.append(HRFlowable(width="100%", thickness=0.4, color=RULE, spaceAfter=1 * mm))
        for entry in entries:
            title = entry.get("title") or ""
            employer = entry.get("employer") or ""
            period = entry.get("period") or ""
            if title:
                story.append(Paragraph(_esc(title), styles["job_title"]))
            meta_parts = [p for p in (employer, period) if p]
            if meta_parts:
                story.append(Paragraph(_esc(" — ".join(meta_parts)), styles["job_meta"]))
            for bullet in entry.get("bullets") or []:
                story.append(Paragraph(f"• {_esc(str(bullet))}", styles["bullet"]))
            story.append(Spacer(1, 1 * mm))

    doc.build(story)
    return path
