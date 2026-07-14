"""CLI for Hanou Career Coach."""

from __future__ import annotations

import logging
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import typer
from rich.console import Console
from rich.table import Table

from hanou_career.config import OUTPUT_DIR, get_settings
from hanou_career.cv.master import build_master_pdf, load_candidate, load_master_cv
from hanou_career.cv.tailor import write_tailored_artifacts
from hanou_career.jobs.cache import load_jobs, load_ranked, save_jobs, save_ranked
from hanou_career.jobs.fresh_sources import fetch_live_clinic_jobs
from hanou_career.jobs.freshness import filter_fresh
from hanou_career.jobs.hano_db import fetch_hano_jobs
from hanou_career.jobs.normalize import merge_jobs
from hanou_career.jobs.online_search import fetch_online_jobs, load_manual_inbox
from hanou_career.jobs.rank import rank_jobs
from hanou_career.jobs.verify import filter_live_jobs
from hanou_career.report.build_html import build_report

app = typer.Typer(
    name="hanou-career",
    help="Career coach for Mohammad Fares Hanou — CVs, job ranking, HTML dashboard.",
    no_args_is_help=True,
)
console = Console()
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

CACHE_PATH = OUTPUT_DIR / "jobs_cache.json"
RANKED_PATH = OUTPUT_DIR / "ranked.json"


def do_ingest(*, skip_online: bool = False, skip_hano: bool = False) -> int:
    settings = get_settings()
    jobs = []

    console.print("[bold]Live clinic/ATS boards (Agaplesion, MediClin, …)…[/bold]")
    jobs.extend(fetch_live_clinic_jobs())

    if not skip_hano:
        console.print("[bold]Fetching Hano DB / JSONL (non-stale sources)…[/bold]")
        jobs.extend(fetch_hano_jobs())

    jobs.extend(load_manual_inbox())
    if not skip_online and settings.hanou_include_arbeitsagentur:
        console.print("[bold]Online search (Arbeitsagentur)…[/bold]")
        jobs.extend(fetch_online_jobs())
    elif not skip_online:
        console.print(
            "[yellow]Skipping Arbeitsagentur online search "
            "(ghost 410 listings). Set HANOU_INCLUDE_ARBEITSAGENTUR=true to force.[/yellow]"
        )

    merged = merge_jobs(jobs)
    console.print(f"Merged raw pool: {len(merged)}")

    before = len(merged)
    merged = filter_fresh(
        merged,
        max_age_days=settings.hanou_max_age_days,
        allow_missing_date=True,
    )
    console.print(
        f"Freshness (≤{settings.hanou_max_age_days}d or undated live): "
        f"{len(merged)} kept, {before - len(merged)} dropped by date"
    )

    if settings.hanou_verify_urls:
        console.print("[bold]Verifying job URLs are still live…[/bold]")
        # Always verify Arbeitsagentur — their search API returns many ghosts.
        aa_urls = {
            j.url for j in merged
            if "arbeitsagentur" in j.source or "arbeitsagentur.de" in j.url
        }
        aa = [j for j in merged if j.url in aa_urls]
        other = [j for j in merged if j.url not in aa_urls]
        live_aa, dead_aa = filter_live_jobs(aa)
        live_other, dead_other = filter_live_jobs(other)
        merged = merge_jobs(live_aa + live_other)
        console.print(
            f"URL verify: kept {len(merged)} "
            f"(dropped AA={dead_aa}, other={dead_other})"
        )

    save_jobs(CACHE_PATH, merged)
    console.print(f"[green]Saved {len(merged)} live jobs → {CACHE_PATH}[/green]")
    return len(merged)


def do_rank(*, top_n: int | None = None) -> int:
    settings = get_settings()
    n = top_n if isinstance(top_n, int) and top_n > 0 else settings.hanou_top_n
    jobs = load_jobs(CACHE_PATH)
    if not jobs:
        console.print("[yellow]No cache — running ingest first…[/yellow]")
        do_ingest()
        jobs = load_jobs(CACHE_PATH)
    candidate = load_candidate()
    ranked = rank_jobs(jobs, candidate=candidate, top_n=n)
    save_ranked(RANKED_PATH, ranked)

    table = Table(title=f"Top {len(ranked)} jobs for Hanou")
    table.add_column("Score", justify="right")
    table.add_column("Elig.")
    table.add_column("Title")
    table.add_column("Employer")
    table.add_column("Where")
    for r in ranked[:15]:
        table.add_row(
            str(r.score),
            r.eligibility,
            r.job.title[:48],
            (r.job.employer or "—")[:28],
            (r.job.location or "—")[:24],
        )
    console.print(table)
    console.print(f"[green]Wrote {RANKED_PATH}[/green]")
    return len(ranked)


def do_tailor() -> int:
    ranked = load_ranked(RANKED_PATH)
    if not ranked:
        console.print("[yellow]No ranked.json — running rank…[/yellow]")
        do_rank()
        ranked = load_ranked(RANKED_PATH)
    candidate = load_candidate()
    master = load_master_cv()
    build_master_pdf()
    keep_slugs = set()
    for r in ranked:
        job_dir = write_tailored_artifacts(r, candidate=candidate, master=master)
        keep_slugs.add(job_dir.name)
        console.print(f"  · {job_dir.name}")

    jobs_root = OUTPUT_DIR / "jobs"
    removed = 0
    if jobs_root.is_dir():
        import shutil

        for path in jobs_root.iterdir():
            if path.is_dir() and path.name not in keep_slugs:
                shutil.rmtree(path, ignore_errors=True)
                removed += 1
    console.print(
        f"[green]Tailored {len(ranked)} job CVs under {jobs_root} "
        f"(removed {removed} outdated folders)[/green]"
    )
    return len(ranked)


def do_report() -> None:
    ranked = load_ranked(RANKED_PATH)
    if not ranked:
        console.print("[red]No ranked jobs. Run: hanou-career rank[/red]")
        raise typer.Exit(1)
    index = build_report(ranked)
    console.print(f"[green]Dashboard → {index}[/green]")


def do_run_all(*, skip_online: bool = False) -> None:
    do_ingest(skip_online=skip_online)
    do_rank()
    path = build_master_pdf()
    console.print(f"[green]Master CV → {path}[/green]")
    do_tailor()
    do_report()
    console.print("[bold green]Done. Open with: hanou-career serve[/bold green]")


@app.command("ingest")
def ingest_cmd(
    skip_online: bool = typer.Option(False, help="Skip Arbeitsagentur online search"),
    skip_hano: bool = typer.Option(False, help="Skip Hano Postgres"),
) -> None:
    """Pull jobs from Hano DB + online search (+ manual inbox)."""
    do_ingest(skip_online=skip_online, skip_hano=skip_hano)


@app.command("rank")
def rank_cmd(
    top: int | None = typer.Option(None, help="Max ranked jobs (default from env)"),
) -> None:
    """Score jobs for Hanou (Berufserlaubnis-aware)."""
    do_rank(top_n=top)


@app.command("build-master")
def build_master_cmd() -> None:
    """Build the generic German Lebenslauf PDF."""
    path = build_master_pdf()
    console.print(f"[green]Master CV → {path}[/green]")


@app.command("tailor")
def tailor_cmd() -> None:
    """Create per-job tailored CVs + gaps.md."""
    do_tailor()


@app.command("report")
def report_cmd() -> None:
    """Rebuild HTML dashboard."""
    do_report()


@app.command("run-all")
def run_all_cmd(
    skip_online: bool = typer.Option(False, help="Skip online search"),
) -> None:
    """Full pipeline: ingest → rank → master CV → tailor → report."""
    do_run_all(skip_online=skip_online)


@app.command("serve")
def serve_cmd(
    open_browser: bool = typer.Option(True, help="Open browser to the dashboard"),
) -> None:
    """Serve the output/ dashboard over HTTP."""
    settings = get_settings()
    root = OUTPUT_DIR
    if not (root / "index.html").is_file():
        console.print("[yellow]No index.html — running report…[/yellow]")
        if RANKED_PATH.is_file():
            do_report()
        else:
            do_run_all()

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)

        def log_message(self, fmt: str, *args) -> None:  # noqa: A003
            console.print(f"[dim]{args[0]} {args[1]}[/dim]")

    host = settings.hanou_serve_host
    port = settings.hanou_serve_port
    url = f"http://{host}:{port}/"
    server = ThreadingHTTPServer((host, port), Handler)
    console.print(f"[bold]Serving {root} at {url}[/bold] (Ctrl+C to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        console.print("\nStopped.")
        server.server_close()


@app.command("publish")
def publish_cmd(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Stage files only; do not push to GitHub"
    ),
) -> None:
    """Push output/ dashboard to GitHub Pages (gh-pages branch)."""
    from hanou_career.report.publish_pages import publish_pages

    try:
        url = publish_pages(dry_run=dry_run)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Publish failed: {exc}[/red]")
        raise typer.Exit(1) from exc
    if dry_run:
        console.print(f"[yellow]{url}[/yellow]")
    else:
        console.print(
            f"[bold green]Published[/bold green] — live in ~1 minute at {url}"
        )


if __name__ == "__main__":
    app()
