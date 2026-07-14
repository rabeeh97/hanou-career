"""Build static HTML dashboard linking jobs to CV artifacts."""

from __future__ import annotations

import html
from pathlib import Path

from hanou_career.config import OUTPUT_DIR
from hanou_career.jobs.schema import RankedJob


def _badge(eligibility: str) -> str:
    colors = {
        "eligible": ("#d8f3e8", "#0d5c45"),
        "risky": ("#fff3cd", "#856404"),
        "blocked": ("#f8d7da", "#721c24"),
    }
    bg, fg = colors.get(eligibility, ("#eee", "#333"))
    return (
        f'<span class="badge" style="background:{bg};color:{fg}">'
        f"{html.escape(eligibility)}</span>"
    )


def build_job_notes_html(ranked: RankedJob, gaps: list[str], job_dir: Path) -> str:
    job = ranked.job
    gap_lis = "\n".join(f"<li>{html.escape(g)}</li>" for g in gaps)
    matched = ", ".join(html.escape(m) for m in ranked.matched) or "—"
    risks = ", ".join(html.escape(r) for r in ranked.risks) or "—"
    desc = html.escape((job.description or "")[:4000])
    slug = html.escape(job.slug)
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{html.escape(job.title)} — Hanou Career</title>
  <link rel="stylesheet" href="../../assets/style.css"/>
</head>
<body data-job-id="{slug}">
  <header class="top">
    <a href="../../index.html">← Alle Empfehlungen</a>
    <h1>{html.escape(job.title)}</h1>
    <p class="meta">{html.escape(job.employer or "—")} · {html.escape(job.location or "—")}</p>
    <p>{_badge(ranked.eligibility)} <strong>Score {ranked.score}/100</strong>
      <span class="read-pill" hidden>Gelesen</span></p>
    <p class="actions">
      <button type="button" class="btn ghost js-mark-read" data-job-id="{slug}">Als gelesen markieren</button>
      <button type="button" class="btn ghost js-mark-unread" data-job-id="{slug}" hidden>Als ungelesen</button>
    </p>
  </header>
  <main class="wrap">
    <section class="card">
      <h2>Downloads</h2>
      <ul class="links">
        <li><a href="cv.pdf">Maßgeschneiderter Lebenslauf (PDF)</a></li>
        <li><a href="../../master_cv.pdf">Master-Lebenslauf (PDF)</a></li>
        <li><a href="gaps.md">Gap-Hinweise (Markdown)</a></li>
        <li><a href="{html.escape(job.url)}" target="_blank" rel="noopener">Original-Stellenanzeige ↗</a></li>
      </ul>
    </section>
    <section class="card">
      <h2>Warum dieser Score?</h2>
      <p>{html.escape(ranked.rationale)}</p>
      <p><strong>Matched:</strong> {matched}</p>
      <p><strong>Risiken:</strong> {risks}</p>
    </section>
    <section class="card">
      <h2>Was am CV ändern?</h2>
      <ol>{gap_lis}</ol>
    </section>
    <section class="card">
      <h2>Stellenübersicht</h2>
      <p class="desc">{desc}</p>
      <p class="muted">Quelle: {html.escape(job.source)}</p>
    </section>
  </main>
  <script src="../../assets/read-state.js" defer></script>
</body>
</html>
"""


def build_index_html(ranked: list[RankedJob]) -> str:
    from datetime import date

    today = date.today().isoformat()
    cards: list[str] = []
    for r in ranked:
        job = r.job
        slug = html.escape(job.slug)
        href = f"jobs/{slug}/notes.html"
        cards.append(
            f"""
      <article class="job-card" data-job-id="{slug}">
        <div class="score">{r.score}</div>
        <div class="body">
          <div class="card-head">
            <h2><a href="{href}">{html.escape(job.title)}</a></h2>
            <span class="read-pill" hidden>Gelesen</span>
          </div>
          <p class="meta">{html.escape(job.employer or "—")} · {html.escape(job.location or "—")}</p>
          <p>{_badge(r.eligibility)} <span class="src">{html.escape(job.source)}</span></p>
          <p class="rationale">{html.escape(r.rationale)}</p>
          <p class="actions">
            <a class="btn" href="{href}">Details & Gaps</a>
            <a class="btn ghost" href="jobs/{slug}/cv.pdf">CV PDF</a>
            <a class="btn ghost" href="{html.escape(job.url)}" target="_blank" rel="noopener">Anzeige</a>
            <button type="button" class="btn ghost js-mark-read" data-job-id="{slug}">Gelesen</button>
            <button type="button" class="btn ghost js-mark-unread" data-job-id="{slug}" hidden>Ungelesen</button>
          </p>
        </div>
      </article>"""
        )
    cards_html = "\n".join(cards) if cards else "<p>Keine gerankten Jobs. Zuerst <code>hanou-career run-all</code> ausführen.</p>"
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Hanou Career Coach — Empfehlungen</title>
  <link rel="stylesheet" href="assets/style.css"/>
</head>
<body>
  <header class="hero">
    <p class="eyebrow">Hanou Career Coach</p>
    <h1>Mohammad Fares Hanou</h1>
    <p class="lede">Nur Niedersachsen · live geprüfte Links · Berufserlaubnis · Master- & Job-CVs</p>
    <p class="actions hero-actions">
      <a class="btn" href="master_cv.pdf">Master-Lebenslauf</a>
      <a class="btn ghost" href="ranked.json">ranked.json</a>
    </p>
  </header>
  <main class="wrap">
    <div class="list-toolbar">
      <p class="count" id="job-count">{len(ranked)} Empfehlungen · Stand {today} · nur noch erreichbare Anzeigen</p>
      <div class="filter-bar" role="group" aria-label="Gelesen-Filter">
        <button type="button" class="chip is-active" data-filter="unread">Ungelesen</button>
        <button type="button" class="chip" data-filter="all">Alle</button>
        <button type="button" class="chip" data-filter="read">Gelesen</button>
        <button type="button" class="chip danger" id="clear-read">Gelesen zurücksetzen</button>
      </div>
      <p class="muted filter-hint">„Gelesen“ bleibt in diesem Browser (localStorage) — GitHub Pages speichert nichts serverseitig.</p>
    </div>
    <div class="job-list">
      {cards_html}
    </div>
    <p class="empty-filter" id="empty-filter" hidden>Keine Stellen in diesem Filter. Wechsle auf „Alle“ oder „Ungelesen“.</p>
  </main>
  <footer class="foot">
    <p>Keine Approbation · Berufserlaubnis vorhanden · FSP bestanden · Anerkennung läuft</p>
  </footer>
  <script src="assets/read-state.js" defer></script>
</body>
</html>
"""


CSS = """
:root {
  --bg: #eef3f6;
  --ink: #142029;
  --muted: #5b6b76;
  --accent: #0b6e6a;
  --card: #ffffff;
  --line: #c9d4dc;
  --display: "Source Serif 4", "Libre Baskerville", "Georgia", serif;
  --sans: "Source Sans 3", "IBM Plex Sans", "Helvetica Neue", Helvetica, Arial, sans-serif;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: var(--sans);
  color: var(--ink);
  background:
    linear-gradient(165deg, #d7e8e6 0%, transparent 42%),
    linear-gradient(340deg, #d4dde6 0%, transparent 40%),
    var(--bg);
  line-height: 1.5;
}
.hero {
  padding: 3rem 1.5rem 2rem;
  max-width: 920px;
  margin: 0 auto;
}
.eyebrow {
  font-size: 0.75rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent);
  margin: 0 0 0.5rem;
}
.hero h1 {
  font-family: var(--display);
  font-size: clamp(2rem, 4vw, 2.75rem);
  margin: 0 0 0.5rem;
  font-weight: 600;
}
.lede { color: var(--muted); max-width: 36rem; margin: 0 0 1.25rem; }
.wrap { max-width: 920px; margin: 0 auto; padding: 0 1.5rem 3rem; }
.count { color: var(--muted); font-size: 0.9rem; margin: 0; }
.list-toolbar { margin-bottom: 0.75rem; }
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin: 0.75rem 0 0.35rem;
}
.filter-hint { font-size: 0.8rem; margin: 0.35rem 0 0; }
.chip {
  appearance: none;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink);
  border-radius: 4px;
  padding: 0.35rem 0.7rem;
  font: inherit;
  font-size: 0.82rem;
  cursor: pointer;
}
.chip.is-active {
  border-color: var(--accent);
  color: var(--accent);
  background: #e7f5f3;
}
.chip.danger { color: #8a3b2b; border-color: #e0b8ae; }
.chip.danger:hover { background: #fceeed; }
button.btn {
  appearance: none;
  border: none;
  font: inherit;
  cursor: pointer;
}
button.btn.ghost {
  background: transparent;
  color: var(--accent);
  border: 1px solid var(--accent);
}
.job-list { display: flex; flex-direction: column; gap: 1rem; margin-top: 1rem; }
.job-card {
  display: grid;
  grid-template-columns: 4.5rem 1fr;
  gap: 1rem;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 1rem 1.15rem;
  transition: opacity 0.2s ease, border-color 0.2s ease;
}
.job-card.is-read {
  opacity: 0.55;
  border-style: dashed;
}
.job-card.is-hidden { display: none; }
.card-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.5rem 0.75rem;
  margin-bottom: 0.25rem;
}
.card-head h2 { margin: 0; flex: 1 1 auto; }
.read-pill {
  display: inline-block;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--muted);
  border: 1px solid var(--line);
  border-radius: 3px;
  padding: 0.12rem 0.4rem;
}
.empty-filter {
  color: var(--muted);
  margin-top: 1.5rem;
  font-size: 0.95rem;
}
.score {
  font-family: var(--display);
  font-size: 1.75rem;
  color: var(--accent);
  font-weight: 600;
  line-height: 1;
  padding-top: 0.2rem;
}
.job-card h2 { font-size: 1.1rem; margin: 0 0 0.25rem; font-family: var(--display); }
.job-card h2 a { color: inherit; text-decoration: none; }
.job-card h2 a:hover { color: var(--accent); }
.meta, .muted, .src { color: var(--muted); font-size: 0.9rem; }
.rationale { font-size: 0.92rem; margin: 0.5rem 0; }
.badge {
  display: inline-block;
  font-size: 0.7rem;
  font-weight: 600;
  padding: 0.15rem 0.45rem;
  border-radius: 3px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-right: 0.4rem;
}
.btn {
  display: inline-block;
  background: var(--accent);
  color: #f2fffe;
  text-decoration: none;
  padding: 0.45rem 0.85rem;
  border-radius: 4px;
  font-size: 0.85rem;
  margin-right: 0.35rem;
  margin-top: 0.35rem;
}
.btn.ghost {
  background: transparent;
  color: var(--accent);
  border: 1px solid var(--accent);
}
.card {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 1.15rem 1.25rem;
  margin-bottom: 1rem;
}
.card h2 { font-family: var(--display); font-size: 1.15rem; margin-top: 0; }
.top { max-width: 920px; margin: 0 auto; padding: 2rem 1.5rem 0.5rem; }
.top a { color: var(--accent); }
.foot {
  text-align: center;
  color: var(--muted);
  font-size: 0.8rem;
  padding: 1rem 1.5rem 2.5rem;
}
.links { padding-left: 1.1rem; }
.desc { white-space: pre-wrap; font-size: 0.92rem; }
@media (max-width: 640px) {
  .job-card { grid-template-columns: 1fr; }
}
"""


READ_STATE_JS = r"""
(function () {
  var STORAGE_KEY = "hanou-career:readJobs:v1";
  var FILTER_KEY = "hanou-career:readFilter:v1";

  function loadRead() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      var arr = raw ? JSON.parse(raw) : [];
      return new Set(Array.isArray(arr) ? arr : []);
    } catch (e) {
      return new Set();
    }
  }

  function saveRead(set) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(set)));
  }

  function loadFilter() {
    var v = localStorage.getItem(FILTER_KEY);
    return v === "all" || v === "read" || v === "unread" ? v : "unread";
  }

  function saveFilter(v) {
    localStorage.setItem(FILTER_KEY, v);
  }

  function setHidden(el, hidden) {
    if (!el) return;
    if (hidden) el.setAttribute("hidden", "");
    else el.removeAttribute("hidden");
  }

  function refreshCard(card, readSet) {
    var id = card.getAttribute("data-job-id");
    var isRead = readSet.has(id);
    card.classList.toggle("is-read", isRead);
    var pill = card.querySelector(".read-pill");
    setHidden(pill, !isRead);
    setHidden(card.querySelector(".js-mark-read"), isRead);
    setHidden(card.querySelector(".js-mark-unread"), !isRead);
  }

  function refreshNotesPage(readSet) {
    var id = document.body.getAttribute("data-job-id");
    if (!id) return;
    var isRead = readSet.has(id);
    document.body.classList.toggle("is-read", isRead);
    setHidden(document.querySelector(".read-pill"), !isRead);
    setHidden(document.querySelector(".js-mark-read"), isRead);
    setHidden(document.querySelector(".js-mark-unread"), !isRead);
  }

  function applyFilter(filter, readSet) {
    var cards = document.querySelectorAll(".job-card[data-job-id]");
    var visible = 0;
    cards.forEach(function (card) {
      var id = card.getAttribute("data-job-id");
      var isRead = readSet.has(id);
      var show =
        filter === "all" ||
        (filter === "unread" && !isRead) ||
        (filter === "read" && isRead);
      card.classList.toggle("is-hidden", !show);
      if (show) visible += 1;
    });
    var empty = document.getElementById("empty-filter");
    setHidden(empty, visible !== 0 || cards.length === 0);
    var count = document.getElementById("job-count");
    if (count) {
      var total = cards.length;
      var unread = 0;
      cards.forEach(function (c) {
        if (!readSet.has(c.getAttribute("data-job-id"))) unread += 1;
      });
      var base = count.getAttribute("data-base") || count.textContent;
      if (!count.getAttribute("data-base")) count.setAttribute("data-base", base);
      count.textContent =
        unread + " ungelesen · " + total + " gesamt · Filter: " +
        (filter === "unread" ? "Ungelesen" : filter === "read" ? "Gelesen" : "Alle");
    }
    document.querySelectorAll("[data-filter]").forEach(function (btn) {
      btn.classList.toggle("is-active", btn.getAttribute("data-filter") === filter);
    });
  }

  function paint() {
    var readSet = loadRead();
    document.querySelectorAll(".job-card[data-job-id]").forEach(function (card) {
      refreshCard(card, readSet);
    });
    refreshNotesPage(readSet);
    if (document.querySelector(".job-list")) {
      applyFilter(loadFilter(), readSet);
    }
  }

  function mark(id, asRead) {
    if (!id) return;
    var readSet = loadRead();
    if (asRead) readSet.add(id);
    else readSet.delete(id);
    saveRead(readSet);
    paint();
  }

  document.addEventListener("click", function (ev) {
    var t = ev.target;
    if (!(t instanceof Element)) return;
    var readBtn = t.closest(".js-mark-read");
    if (readBtn) {
      ev.preventDefault();
      mark(readBtn.getAttribute("data-job-id"), true);
      return;
    }
    var unreadBtn = t.closest(".js-mark-unread");
    if (unreadBtn) {
      ev.preventDefault();
      mark(unreadBtn.getAttribute("data-job-id"), false);
      return;
    }
    var filterBtn = t.closest("[data-filter]");
    if (filterBtn) {
      ev.preventDefault();
      saveFilter(filterBtn.getAttribute("data-filter"));
      paint();
      return;
    }
    if (t.closest("#clear-read")) {
      ev.preventDefault();
      if (window.confirm("Alle Gelesen-Markierungen in diesem Browser löschen?")) {
        localStorage.removeItem(STORAGE_KEY);
        paint();
      }
    }
  });

  // Opening a job detail page counts as started review → mark read.
  var detailId = document.body.getAttribute("data-job-id");
  if (detailId) {
    var readSet = loadRead();
    if (!readSet.has(detailId)) {
      readSet.add(detailId);
      saveRead(readSet);
    }
  }

  paint();
})();
"""


def build_report(ranked: list[RankedJob], *, output_root: Path | None = None) -> Path:
    root = output_root or OUTPUT_DIR
    root.mkdir(parents=True, exist_ok=True)
    assets = root / "assets"
    assets.mkdir(exist_ok=True)
    (assets / "style.css").write_text(CSS, encoding="utf-8")
    (assets / "read-state.js").write_text(READ_STATE_JS, encoding="utf-8")

    (root / "index.html").write_text(build_index_html(ranked), encoding="utf-8")

    for r in ranked:
        job_dir = root / "jobs" / r.job.slug
        job_dir.mkdir(parents=True, exist_ok=True)
        gaps: list[str] = []
        job_json = job_dir / "job.json"
        if job_json.is_file():
            import json

            data = json.loads(job_json.read_text(encoding="utf-8"))
            gaps = list(data.get("gaps") or [])
        (job_dir / "notes.html").write_text(
            build_job_notes_html(r, gaps, job_dir), encoding="utf-8"
        )
    return root / "index.html"
