"""Niedersachsen geo helpers for hard-filtering jobs."""

from __future__ import annotations

from hanou_career.jobs.schema import NormalizedJob

NI_CITIES = {
    "bad harzburg",
    "goslar",
    "braunschweig",
    "hildesheim",
    "göttingen",
    "gottingen",
    "wolfenbüttel",
    "wolfenbuettel",
    "salzgitter",
    "hannover",
    "hanover",
    "oldenburg",
    "osnabrück",
    "osnabruck",
    "celle",
    "lüneburg",
    "lueneburg",
    "stade",
    "cuxhaven",
    "wilhelmshaven",
    "delmenhorst",
    "emden",
    "verden",
    "nienburg",
    "hameln",
    "holzminden",
    "northeim",
    "einbeck",
    "peine",
    "gifhorn",
    "wolfsburg",
    "helmstedt",
    "cloppenburg",
    "vechta",
    "diepholz",
    "syke",
    "lehrte",
    "laatzen",
    "garbsen",
    "seelze",
    "barsinghausen",
    "springe",
    "burgdorf",
    "walsrode",
    "soltau",
    "uelzen",
    "buxtehude",
    "winsen",
    "papenburg",
    "meppen",
    "lingen",
    "nordhorn",
    "aurich",
    "leer",
    "norden",
    "jever",
    "varel",
    "seesen",
    "braunlage",
    "osterode",
    "duderstadt",
    "hann. münden",
    "hann muenden",
    "münden",
    "muenden",
    "bad fallingbostel",
    "fallingbostel",
    "wunstorf",
    "ronnenberg",
    "hemmingen",
    "isernhagen",
    "burgwedel",
    "clausthal-zellerfeld",
    "varel",
}

# Common Niedersachsen PLZ prefixes
NI_PLZ_PREFIXES = {"26", "27", "28", "29", "30", "31", "37", "38", "49"}


def is_niedersachsen(job: NormalizedJob) -> bool:
    bl = (job.bundesland or "").lower().strip()
    if "niedersachsen" in bl or bl in {"ni", "nds"}:
        return True

    city = (job.city or "").lower().strip()
    if city in NI_CITIES:
        return True

    loc = (job.location or "").lower()
    if "niedersachsen" in loc:
        return True
    for c in NI_CITIES:
        if c and (city == c or f", {c}" in loc or loc.startswith(c) or f" {c}" in f" {loc}"):
            if c in loc or city == c:
                return True

    blob = job.text_blob()
    if "niedersachsen" in blob:
        return True

    # PLZ from raw payloads
    for value in (job.raw or {}).values():
        if not isinstance(value, dict):
            continue
        plz = str(value.get("plz") or "")[:2]
        if plz in NI_PLZ_PREFIXES:
            return True

    return False
