#!/usr/bin/env python3
"""Local configuration for the CloudStream builder skill on this machine.

This skill is installed as a checkout of the user's own repository
(``altigenay/cloudstream-eklentiler``), so every path defaults to the checkout
itself. Nothing here points at the original author's Windows machine.

Environment overrides (all optional):

  CLOUDSTREAM_REPOS    Colon separated list of local repository directories.
                       Defaults to this checkout.
  CLOUDSTREAM_OUTPUT   Output directory for build jobs. Defaults to the checkout.
  CLOUDSTREAM_BRANCH   Default branch name. Defaults to ``main``.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = Path(os.environ.get("CLOUDSTREAM_OUTPUT") or SKILL_ROOT).expanduser()
DEFAULT_BRANCH = os.environ.get("CLOUDSTREAM_BRANCH", "main")
DEFAULT_SLUG = "altigenay/cloudstream-eklentiler"


def repo_dirs() -> list[Path]:
    """Local repository directories this skill should audit and publish."""
    raw = os.environ.get("CLOUDSTREAM_REPOS", "").strip()
    if not raw:
        return [SKILL_ROOT]
    return [Path(part).expanduser() for part in raw.split(os.pathsep) if part.strip()]


def origin_slug(repo: Path) -> str:
    """``owner/name`` of the repository's origin remote, with a safe fallback."""
    try:
        url = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except Exception:
        return DEFAULT_SLUG
    if url.endswith(".git"):
        url = url[:-4]
    if url.startswith("git@github.com:"):
        return url.split(":", 1)[1]
    if "github.com/" in url:
        return url.split("github.com/", 1)[1].strip("/")
    return DEFAULT_SLUG


def repo_json_url(repo: Path, branch: str | None = None) -> str:
    """Public raw URL of the repository catalog used by CloudStream clients."""
    branch = branch or DEFAULT_BRANCH
    return f"https://raw.githubusercontent.com/{origin_slug(repo)}/{branch}/repo.json"


def repos() -> list[dict]:
    """Repository entries in the shape the audit/heal scripts expect."""
    entries = []
    for path in repo_dirs():
        name = path.name or "repo"
        branch = DEFAULT_BRANCH
        entries.append(
            {
                "name": name,
                "path": path,
                "branch": branch,
                "repo_json": repo_json_url(path, branch),
            }
        )
    return entries


if __name__ == "__main__":
    for entry in repos():
        print(f"{entry['name']}\t{entry['path']}\t{entry['branch']}\t{entry['repo_json']}")
