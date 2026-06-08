"""GitRemote — pluggable target for the Kaizen actuator's change-publishing.

Decouples the self-evolution loop from GitHub. The pr-agent commits the patch on
a branch (host-agnostic), then hands the branch to a GitRemote which publishes
the change and later reports its outcome:

  - GithubRemote: `gh auth setup-git` → `git push` → `gh pr create --head` (PR
    URL); outcome via `gh pr view --json state` (merged / closed / open).
  - KotobaRemote: GitHub-INDEPENDENT. Pushes the committed branch into kotoba's
    content-addressed Datom store via the kotoba-git write surface (the
    `kotoba git import` CLI), so the loop self-evolves with NO GitHub / GHCR /
    token dependency. The "change" is a kotoba ref; its outcome is a kotoba
    approval marker (Council / operator), not a GitHub merge.

Selected by env ``KAIZEN_GIT_REMOTE`` (github | kotoba; default github).
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger("kotodama.organism.kaizen.git_remote")


class GitRemote(Protocol):
    name: str

    def open_change(
        self, *, repo_root: Path, branch: str, title: str, body: str, labels: list[str]
    ) -> str:
        """Publish the already-committed `branch` as a reviewable change.
        Returns a reference (PR URL for GitHub, kotoba ref/CID for kotoba)."""
        ...

    def change_state(self, ref_or_branch: str, *, repo_root: Path) -> str:
        """Resolve a published change to: merged | closed | open | unknown.
        merged → accepted (positive fitness), closed → rejected."""
        ...


class GithubRemote:
    """Opens a real GitHub PR (the original actuator behavior)."""

    name = "github"

    def open_change(
        self, *, repo_root: Path, branch: str, title: str, body: str, labels: list[str]
    ) -> str:
        # Authenticate git pushes via the gh credential helper (GH_TOKEN).
        subprocess.run(["gh", "auth", "setup-git"], check=True, cwd=repo_root, capture_output=True)
        subprocess.run(
            ["git", "push", "-u", "origin", branch], check=True, cwd=repo_root, capture_output=True
        )
        cmd = ["gh", "pr", "create", "--head", branch, "--title", title, "--body", body]
        for lb in labels:
            cmd += ["--label", lb]
        result = subprocess.run(cmd, check=True, cwd=repo_root, capture_output=True, text=True)
        out = result.stdout.strip()
        return out.splitlines()[-1] if out else "PR created"

    def change_state(self, ref_or_branch: str, *, repo_root: Path) -> str:
        try:
            out = subprocess.run(
                ["gh", "pr", "view", ref_or_branch, "--json", "state", "--jq", ".state"],
                cwd=repo_root, capture_output=True, text=True, timeout=20,
            )
            s = (out.stdout or "").strip().upper()
        except Exception:  # noqa: BLE001
            return "unknown"
        return {"MERGED": "merged", "CLOSED": "closed", "OPEN": "open"}.get(s, "unknown")


class KotobaRemote:
    """GitHub-independent: push the committed branch into kotoba's content-
    addressed Datom store via the kotoba-git write surface (no GitHub).

    Mechanism (per the kotoba-git write API — GitStore.import_repo / put_ref):
    shells the kotoba CLI `kotoba git import <repo>/.git --graph <graph>`, which
    ingests the branch's objects + refs as content-addressed `:git/*` Datoms.
    The command is configurable via ``KAIZEN_KOTOBA_GIT_CMD`` (default
    "kotoba git import") so the binary path / subcommand can be pointed at the
    operator's kotoba build. Returns the kotoba ref (refs/heads/<branch>).
    """

    name = "kotoba"

    def __init__(self, *, graph: str | None = None, kotoba_cmd: str | None = None):
        self.graph = graph or os.environ.get("KAIZEN_KOTOBA_GRAPH", "kaizen:self-evolution")
        self.kotoba_cmd = (kotoba_cmd or os.environ.get("KAIZEN_KOTOBA_GIT_CMD", "kotoba git import")).split()

    def open_change(
        self, *, repo_root: Path, branch: str, title: str, body: str, labels: list[str]
    ) -> str:
        git_dir = str(Path(repo_root) / ".git")
        cmd = [*self.kotoba_cmd, git_dir, "--graph", self.graph, "--ref", f"refs/heads/{branch}"]
        logger.info("kotoba push: %s", " ".join(cmd))
        # No GitHub, no token, no network egress to github.com — the change lands
        # in the kotoba content-addressed Datom log on the fleet.
        subprocess.run(cmd, check=True, cwd=repo_root, capture_output=True, text=True)
        return f"kotoba:{self.graph}/refs/heads/{branch}"

    def change_state(self, ref_or_branch: str, *, repo_root: Path) -> str:
        # A kotoba ref is "accepted" when an operator/Council marks it (a
        # :git.ref/approved Datom). Until that approval surface lands, treat it
        # as open (pending). No GitHub call.
        marker = os.environ.get("KAIZEN_KOTOBA_APPROVED_REFS", "")
        approved = {r.strip() for r in marker.split(",") if r.strip()}
        rejected_marker = os.environ.get("KAIZEN_KOTOBA_REJECTED_REFS", "")
        rejected = {r.strip() for r in rejected_marker.split(",") if r.strip()}
        if ref_or_branch in approved:
            return "merged"
        if ref_or_branch in rejected:
            return "closed"
        return "open"


def select_remote(name: str | None = None) -> GitRemote:
    """Resolve the GitRemote from name / KAIZEN_GIT_REMOTE env (default github)."""
    n = (name or os.environ.get("KAIZEN_GIT_REMOTE", "github")).strip().lower()
    if n == "kotoba":
        return KotobaRemote()
    return GithubRemote()


__all__ = ["GitRemote", "GithubRemote", "KotobaRemote", "select_remote"]
