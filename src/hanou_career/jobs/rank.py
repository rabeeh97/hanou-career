"""BE-aware ranking for Mohammad Fares Hanou (Niedersachsen-focused)."""

from __future__ import annotations

import re
from typing import Any

from hanou_career.jobs.geo import is_niedersachsen
from hanou_career.jobs.schema import NormalizedJob, RankedJob

TOKEN_RE = re.compile(r"[a-z0-9äöüß]{2,}", re.I)

POSITIVE_CLINICAL = (
    "geriatrie",
    "geriatr",
    "reha",
    "rehabilitation",
    "innere",
    "internist",
    "visite",
    "sonographie",
    "anamnese",
    "multimorbid",
    "aufnahme",
    "assistenzarzt",
    "assistenzärztin",
    "weiterbildung",
    "orthopäd",
    "unfall",
    "bewegungsapparat",
    "kardiolog",
    "neuro",
)

GEO_BOOST = (
    "bad harzburg",
    "harzburg",
    "goslar",
    "harz",
    "niedersachsen",
    "braunschweig",
    "hildesheim",
    "göttingen",
    "gottingen",
    "wolfenbüttel",
    "salzgitter",
    "hannover",
    "oldenburg",
    "osnabrück",
    "osnabruck",
    "wolfsburg",
    "celle",
    "lüneburg",
    "cuxhaven",
    "holzminden",
    "northeim",
    "barsinghausen",
)

NEGATIVE_SENIORITY = (
    "chefarzt",
    "chefärztin",
    "oberarzt",
    "oberärztin",
    "leitender",
    "facharztstelle",
    "fachärztin für",
)

NEGATIVE_NON_MD = (
    "pflegefachkraft",
    "pflegefachkraft,",
    "altenpfleger",
    "physiotherapeut",
    "ergotherapeut",
    "logopäde",
    " MFA ",
    "mfa ",
    "teamassistenz",
    "medizinischer fachangestellter",
    "medizinische fachangestellte",
    "krankenpfleger",
    "sekretariat",
    "operations-technische",
    "ata ",
    "ota ",
)

RECRUITER_HINTS = (
    "ffd fachkräfte",
    "ffd fachkraefte",
    "personalvermittlung",
    "recruiting",
    "zeitarbeit",
    "ärztevermittlung",
    "arztevermittlung",
)



def is_junior_clinical_role(title: str) -> bool:
    """Keep Assistenzarzt / AiW / Hospitation; drop pure Facharzt/Oberarzt/Chefarzt."""
    t = (title or "").lower()
    if t.startswith("klinik-ziel"):
        return True  # discovery leads
    if any(k in t for k in ("oberarzt", "oberärztin", "chefarzt", "chefärztin")):
        return "assistenz" in t
    has_fach = ("facharzt" in t or "fachärztin" in t)
    has_assistenz = "assistenz" in t
    has_aiw = any(
        k in t
        for k in (
            "arzt in weiterbildung",
            "ärztin in weiterbildung",
            "stationsarzt",
            "stationsärztin",
            "hospitat",
        )
    )
    # "Zusatzweiterbildung" on a Facharzt job is still a Facharzt role.
    has_wb = ("weiterbildung" in t and "zusatzweiterbildung" not in t and "zusatz-weiterbildung" not in t)
    if has_fach and not (has_assistenz or has_aiw):
        return False
    if has_assistenz or has_aiw or (has_wb and not has_fach):
        return True
    if ("arzt" in t or "ärztin" in t) and not has_fach:
        return True
    return False


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in TOKEN_RE.findall(text or "")}


def rank_jobs(
    jobs: list[NormalizedJob],
    *,
    candidate: dict[str, Any],
    top_n: int = 100,
    niedersachsen_only: bool = True,
) -> list[RankedJob]:
    skill_tokens = set()
    for s in candidate.get("skills") or []:
        skill_tokens |= _tokenize(str(s))
    for s in candidate.get("specializations_tokens") or []:
        skill_tokens |= _tokenize(str(s))
    for role in candidate.get("target_roles") or []:
        skill_tokens |= _tokenize(str(role))

    preferred_flat: set[str] = set()
    for r in candidate.get("preferred_regions") or []:
        preferred_flat |= _tokenize(str(r))

    if niedersachsen_only:
        scoped = [j for j in jobs if is_niedersachsen(j)]
    else:
        scoped = list(jobs)

    ranked: list[RankedJob] = []
    for job in scoped:
        blob = job.text_blob()
        score = 40  # NI-scoped baseline
        matched: list[str] = ["Niedersachsen"]
        risks: list[str] = []
        eligibility = "eligible"

        if not is_junior_clinical_role(job.title):
            ranked.append(
                RankedJob(
                    job=job,
                    score=5,
                    rationale="Zu fortgeschritten (Facharzt/Oberarzt/Chefarzt) — Zielprofil: Assistenzarzt/AiW.",
                    matched=["Niedersachsen"],
                    risks=[
                        "Zu fortgeschritten (Facharzt/Oberarzt/Chefarzt) — Zielprofil: Assistenzarzt/AiW."
                    ],
                    eligibility="blocked",
                )
            )
            continue
        if job.source.startswith("hano-jsonl:klinikradar") or job.title.startswith(
            "Klinik-Ziel"
        ):
            score = 45  # useful leads, but below concrete Assistenzarzt ads
            matched.append("Klinikradar-Lead")
            risks.append(
                "Klinikradar-Lead — aktive Stellenausschreibung auf Klinikseite prüfen."
            )

        # Hard / soft licensing gates
        if job.requires_approbation is True and not job.accepts_berufserlaubnis:
            eligibility = "blocked"
            score = 5
            risks.append("Stelle verlangt Approbation ohne erkennbaren Berufserlaubnis-Pfad.")
        elif job.requires_approbation is True and job.accepts_berufserlaubnis:
            eligibility = "risky"
            score += 5
            matched.append("Approbation genannt, Berufserlaubnis jedoch akzeptiert")
        elif job.accepts_berufserlaubnis:
            score += 22
            matched.append("Berufserlaubnis / Anerkennung-freundlich")
            if eligibility != "blocked":
                eligibility = "eligible"
        elif "approbation" in blob and "berufserlaubnis" not in blob:
            eligibility = "risky"
            score -= 12
            risks.append("Approbation erwähnt — BE-Pfad unklar; Anschreiben vorsichtig formulieren.")

        # Clinical fit
        for kw in POSITIVE_CLINICAL:
            if kw in blob:
                score += 4
                matched.append(kw)
        matched = list(dict.fromkeys(matched))[:12]

        overlap = skill_tokens.intersection(_tokenize(blob))
        score += min(20, len(overlap) * 2)

        # Geography
        geo_hit = False
        for g in GEO_BOOST:
            if g in blob:
                score += 6
                geo_hit = True
                matched.append(g)
                break
        if preferred_flat and preferred_flat.intersection(_tokenize(blob)):
            score += 4
            geo_hit = True
        if not geo_hit:
            score -= 2

        # Seniority / non-MD penalties
        for bad in NEGATIVE_SENIORITY:
            if bad in blob:
                score -= 18
                risks.append(f"Senioritäts-Signal: {bad}")
                break
        for bad in NEGATIVE_NON_MD:
            if bad.lower() in blob:
                score -= 40
                risks.append(f"Eher keine Arztstelle: {bad.strip()}")
                eligibility = "blocked"
                break

        # Title preference
        title_l = job.title.lower()
        if not any(
            k in title_l
            for k in ("arzt", "ärzt", "assistenz", "hospitat", "mediziner", "klinik-ziel")
        ):
            score -= 35
            risks.append("Titel wirkt nicht ärztlich.")
            eligibility = "blocked"

        if "assistenz" in title_l:
            score += 18
            matched.append("Assistenzarzt-Titel")
        if "hospitat" in title_l:
            score += 10
            matched.append("Hospitation")
        if "weiterbildung" in title_l or "stationsarzt" in title_l:
            score += 12
            matched.append("Weiterbildung/Stationsarzt")
        if any(x in title_l for x in ("geriatr", "reha", "innere")):
            score += 8
        if "approbiert" in title_l and "berufserlaubnis" not in blob:
            score -= 15
            risks.append("Titel verlangt Approbierten Arzt — BE ggf. unzureichend.")
            eligibility = "risky" if eligibility == "eligible" else eligibility

        employer_blob = f"{job.employer or ''} {blob}".lower()
        if any(h in employer_blob for h in RECRUITER_HINTS):
            score -= 8
            risks.append("Vermittler-/Agentur-Anzeige — Klinik direkt prüfen.")

        score = int(max(0, min(100, score)))
        if job.source.startswith("hano-jsonl:klinikradar") or job.title.startswith(
            "Klinik-Ziel"
        ):
            # Keep clinic leads, but never above concrete job ads.
            score = min(score, 52)

        bits = []
        if matched:
            bits.append("Passend: " + ", ".join(matched[:6]))
        if risks:
            bits.append("Risiken: " + "; ".join(risks[:3]))
        if not bits:
            bits.append("Eingeschränkte Übereinstimmung mit Profil.")
        rationale = " ".join(bits)

        ranked.append(
            RankedJob(
                job=job,
                score=score,
                rationale=rationale,
                matched=matched,
                risks=risks,
                eligibility=eligibility,
            )
        )

    def _posted_key(r: RankedJob) -> str:
        return r.job.posted_date or ""

    ranked.sort(
        key=lambda r: (r.eligibility != "blocked", r.score, _posted_key(r)),
        reverse=True,
    )
    # Deduplicate near-identical recruiter clones (same title+city)
    deduped: list[RankedJob] = []
    seen_keys: set[str] = set()
    for r in ranked:
        key = "|".join(
            [
                (r.job.title or "").lower().strip()[:80],
                (r.job.city or r.job.location or "").lower().strip()[:40],
                (r.job.employer or "").lower().strip()[:40],
            ]
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(r)

    eligible = [r for r in deduped if r.eligibility != "blocked"]
    blocked = [r for r in deduped if r.eligibility == "blocked"]

    def _is_klinikradar(r: RankedJob) -> bool:
        return "klinikradar" in r.job.source or r.job.title.startswith("Klinik-Ziel")

    concrete = [r for r in eligible if not _is_klinikradar(r)]
    leads = [r for r in eligible if _is_klinikradar(r)]
    lead_slots = min(10, max(0, top_n // 10), len(leads))
    concrete_slots = top_n - lead_slots
    selected = concrete[:concrete_slots] + leads[:lead_slots]
    # Never pad with blocked/non-MD roles — better show fewer live fits.
    # Display order is always score descending (posted_date only as tiebreaker).
    selected.sort(
        key=lambda r: (r.score, _posted_key(r)),
        reverse=True,
    )
    return selected
