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
from hanou_career.jobs.hano_db import fetch_hano_jobs
from hanou_career.jobs.normalize import merge_jobs
from hanou_career.jobs.online_search import fetch_online_jobs, load_manual_inbox
from hanou_career.jobs.rank import rank_jobs
from hanou_career.report.build_html import build_report

app = typer.Typer(
    name="hanou-career",
    help="Career coach for Mohamad Fares Hanou — CVs, job ranking, HTML dashboard.",
    no_args_is_help=True,
)
console = Console()
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

CACHE_PATH = OUTPUT_DIR / "jobs_cache.json"
RANKED_PATH = OUTPUT_DIR / "ranked.json"


def do_ingest(*, skip_online: bool = False, skip_hano: bool = False) -> int:
    jobs = []
    if not skip_hano:
        console.print("[bold]Fetching Hano DB…[/bold]")
        jobs.extend(fetch_hano_jobs())
    if not skip_online:
        console.print("[bold]Online search (Arbeitsagentur)…[/bold]")
        jobs.extend(fetch_online_jobs())
    else:
        jobs.extend(load_manual_inbox())

    merged = merge_jobs(jobs)
    save_jobs(CACHE_PATH, merged)
    console.print(f"[green]Saved {len(merged)} jobs → {CACHE_PATH}[/green]")
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
    for r in ranked:
        job_dir = write_tailored_artifacts(r, candidate=candidate, master=master)
        console.print(f"  · {job_dir.name}")
    console.print(f"[green]Tailored {len(ranked)} job CVs under {OUTPUT_DIR / 'jobs'}[/green]")
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


if __name__ == "__main__":
    app()
