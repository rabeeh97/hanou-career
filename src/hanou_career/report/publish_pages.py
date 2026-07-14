"""Stage output/ and push to the gh-pages branch for GitHub Pages."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from hanou_career.config import OUTPUT_DIR, REPO_ROOT

PAGES_URL = "https://rabeeh97.github.io/hanou-career/"
REMOTE_DEFAULT = "origin"
BRANCH = "gh-pages"

# Heavy / unneeded on the public site
_SKIP_TOP_LEVEL = {"jobs_cache.json"}


def _safe_job_dir(name: str) -> bool:
    return not any(ch in name for ch in (":", "?", "#", "*", "\\"))


def stage_site(src: Path, dest: Path) -> int:
    """Copy a Pages-safe subset of output/ into dest. Returns file count."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    for name in ("index.html", "master_cv.pdf", "ranked.json", "assets"):
        p = src / name
        if not p.exists():
            continue
        target = dest / name
        if p.is_dir():
            shutil.copytree(p, target)
        else:
            shutil.copy2(p, target)

    jobs_src = src / "jobs"
    jobs_dst = dest / "jobs"
    jobs_dst.mkdir(exist_ok=True)
    if jobs_src.is_dir():
        for child in jobs_src.iterdir():
            if not child.is_dir() or child.name.startswith("."):
                continue
            if not _safe_job_dir(child.name):
                continue
            if not any(
                (child / f).exists() for f in ("notes.html", "cv.pdf", "job.json")
            ):
                continue
            shutil.copytree(child, jobs_dst / child.name)

    # Drop accidental jobs_cache if copied
    for skip in _SKIP_TOP_LEVEL:
        bad = dest / skip
        if bad.exists():
            bad.unlink()

    # Fail loud if index still points at broken URL-in-path hrefs
    index = dest / "index.html"
    if index.is_file():
        text = index.read_text(encoding="utf-8")
        if re.search(r'href="jobs/[^"]*https?:', text):
            raise RuntimeError(
                "index.html still has URL-in-path job links; re-run report after "
                "upgrading slug sanitization, then publish again."
            )

    return sum(1 for p in dest.rglob("*") if p.is_file())


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def _git_identity(repo: Path) -> tuple[str, str]:
    name = subprocess.check_output(
        ["git", "-C", str(repo), "log", "-1", "--format=%an"],
        text=True,
    ).strip()
    email = subprocess.check_output(
        ["git", "-C", str(repo), "log", "-1", "--format=%ae"],
        text=True,
    ).strip()
    if not name or not email:
        raise RuntimeError("Could not read git author from the latest commit.")
    return name, email


def publish_pages(
    *,
    remote: str = REMOTE_DEFAULT,
    dry_run: bool = False,
) -> str:
    """Stage output/ and force-push an orphan gh-pages branch. Returns the site URL."""
    src = OUTPUT_DIR
    if not (src / "index.html").is_file():
        raise FileNotFoundError(f"Missing {src / 'index.html'} — run: hanou-career report")

    site_dir = REPO_ROOT / ".site-publish"
    n_files = stage_site(src, site_dir)

    if dry_run:
        return f"dry-run: staged {n_files} files → {site_dir} (not pushed)"

    name, email = _git_identity(REPO_ROOT)
    with tempfile.TemporaryDirectory(prefix="hanou-pages-") as tmp:
        tmp_path = Path(tmp)
        # Copy staged tree into temp so we never disturb the main worktree
        for item in site_dir.iterdir():
            target = tmp_path / item.name
            if item.is_dir():
                shutil.copytree(item, target)
            else:
                shutil.copy2(item, target)

        _run(["git", "init", "-b", BRANCH], cwd=tmp_path)
        _run(["git", "add", "."], cwd=tmp_path)
        _run(
            [
                "git",
                "-c",
                f"user.name={name}",
                "-c",
                f"user.email={email}",
                "commit",
                "-m",
                "Publish career recommendations dashboard.",
            ],
            cwd=tmp_path,
        )
        # Discover remote URL from the main repo
        remote_url = subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "remote", "get-url", remote],
            text=True,
        ).strip()
        _run(["git", "remote", "add", "origin", remote_url], cwd=tmp_path)
        _run(["git", "push", "-u", "origin", f"{BRANCH}:{BRANCH}", "--force"], cwd=tmp_path)

    return PAGES_URL
