# Hanou Career Coach

Sibling project to [Hano](../Hano): helps **Mohammad Fares Hanou** get hired as a physician in Germany with Berufserlaubnis (no Approbation yet).

## What it does

1. **Master Lebenslauf** — German medical CV tuned for BE-eligible roles (Geriatrie / Reha / Innere).
2. **Job intake** — reads scraped jobs from Hano’s Postgres **and** runs fresh Arbeitsagentur searches.
3. **BE-aware ranking** — surfaces openings where he is a strong, honest match.
4. **Per-job tailored CVs** + concrete gap notes.
5. **HTML dashboard** — links each job to its CV PDF and recommendations.

## Share the dashboard

Live site: **https://rabeeh97.github.io/hanou-career/**

Anyone with the link can browse recommendations, download CV PDFs, and open job ads (**Anzeige**). The site is public.

Pushing code to `master` does **not** update the site (`output/` is local/gitignored). After regenerating the dashboard:

```bash
hanou-career publish
```

That force-pushes `output/` to the `gh-pages` branch; GitHub Pages rebuilds automatically within about a minute.

## Quick start

```bash
cd /Users/rabeehjouni/repos/hanou-career
cp .env.example .env

# Option A — reuse sibling Hano venv (recommended if deps already installed):
../Hano/.venv/bin/pip install -e . --no-deps
../Hano/.venv/bin/hanou-career run-all
../Hano/.venv/bin/hanou-career serve

# Option B — dedicated venv:
# python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
# hanou-career run-all && hanou-career serve

# open http://127.0.0.1:8765
```

Jobs come from **Hano Postgres** (if Docker is up), else **`../Hano/var/*.jsonl`**, plus a live **Arbeitsagentur** search. Paste extra leads into `data/search_manual.jsonl`.

## Freshness

Ingest **verifies every job URL** and drops expired Arbeitsagentur ghosts (HTTP 410 / „nicht mehr verfügbar“). Prefer live ATS boards (Agaplesion Softgarden, MediClin, …). Set `HANOU_MAX_AGE_DAYS` (default 90) and `HANOU_VERIFY_URLS=true`.

## CLI

| Command | Purpose |
| --- | --- |
| `hanou-career ingest` | Hano DB + online search → `output/jobs_cache.json` |
| `hanou-career rank` | Score & filter → `output/ranked.json` |
| `hanou-career build-master` | Write `output/master_cv.pdf` |
| `hanou-career tailor` | Per-job `output/jobs/<slug>/{cv.pdf,gaps.md,job.json}` |
| `hanou-career report` | Rebuild `output/index.html` + job notes pages |
| `hanou-career run-all` | Full pipeline |
| `hanou-career serve` | Serve the dashboard |
| `hanou-career publish` | Push `output/` → GitHub Pages |

## Manual job inbox

Append JSON lines to [`data/search_manual.jsonl`](data/search_manual.jsonl):

```json
{"url":"https://...","title":"Assistenzarzt Geriatrie","employer":"...","location":"Bad Harzburg","description":"..."}
```

## Candidate facts (authoritative)

- FSP (Fachsprachprüfung) passed; German C1
- Berufserlaubnis (~2 years); **no Approbation**; Anerkennung in progress
- Hospitation Geriatrie, Herzog-Julius-Klinik, 01.11.2025–30.04.2026

Edit content in [`data/`](data/) — especially `master_cv.yaml` — without touching code.

## License

MIT.
