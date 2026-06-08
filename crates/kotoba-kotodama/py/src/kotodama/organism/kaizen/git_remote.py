"""GitRemote — pluggable target for the Kaizen actuator's change-publishing.

Decouples the self-evolution loop from GitHub. The pr-agent commits the patch on
a branch (host-agnostic), then hands the branch to a GitRemote which publishes
the change and later reports its outcome:

  - GithubRemote: `gh auth setup-git` → `git push` → `gh pr create --head` (PR
    URL); outcome via `gh pr view --json state` (merged / closed / open).
  - KotobaRemote: GitHub-INDEPENDENT. `git push`es the committed branch over the
    kotoba server's git smart-HTTP endpoint (`POST /git/<repo>/git-receive-pack`,
    kotoba-server::git_http → kotoba_git::wire::receive_pack), so every object
    lands as an IPFS block + `:git/*` Datom projection on the running kotoba node
    — NO GitHub / GHCR dependency, a real git-protocol push into the content-
    addressed Datom log. The "change" is a kotoba ref; its outcome is a kotoba
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
    """GitHub-independent: `git push` the committed branch into kotoba's content-
    addressed Datom store over the kotoba server's git smart-HTTP endpoint.

    Mechanism — a *real git push* (no GitHub):
      git push <KAIZEN_KOTOBA_GIT_URL>/git/<repo> refs/heads/<b>:refs/heads/<b>
    hits `POST /git/<repo>/git-receive-pack` (kotoba-server::git_http), which runs
    `kotoba_git::wire::receive_pack` → every object becomes an IPFS block + a
    `:git/*` Datom projection, then `git_persist` snapshots the oid↔cid index +
    refs. The push gate (`push_gate`) authenticates via an operator Bearer JWT
    (``KAIZEN_KOTOBA_GIT_TOKEN``, operator-injected — no platform key, same model
    as GH_TOKEN), or anonymously when the node runs KOTOBA_GIT_ALLOW_ANON_PUSH=1
    (set ``KAIZEN_KOTOBA_GIT_ANON=1`` to skip the auth header).

    Env:
      KAIZEN_KOTOBA_GIT_URL    kotoba server base (default http://127.0.0.1:8080)
      KAIZEN_KOTOBA_REPO       per-repo git Connection name (default "root")
      KAIZEN_KOTOBA_GIT_TOKEN  operator Bearer JWT for the push gate
      KAIZEN_KOTOBA_GIT_ANON   "1" → no auth header (node allows anon push)
    Returns the kotoba ref `kotoba:<repo>/refs/heads/<branch>`.
    """

    name = "kotoba"

    def __init__(self, *, base_url: str | None = None, repo: str | None = None):
        self.base_url = (base_url or os.environ.get("KAIZEN_KOTOBA_GIT_URL", "http://127.0.0.1:8080")).rstrip("/")
        self.repo = repo or os.environ.get("KAIZEN_KOTOBA_REPO", "root")

    def open_change(
        self, *, repo_root: Path, branch: str, title: str, body: str, labels: list[str]
    ) -> str:
        remote_url = f"{self.base_url}/git/{self.repo}"
        refspec = f"refs/heads/{branch}:refs/heads/{branch}"
        cmd = ["git", "push", remote_url, refspec]
        # Operator-injected Bearer JWT for the kotoba push gate (no platform key).
        token = os.environ.get("KAIZEN_KOTOBA_GIT_TOKEN", "")
        anon = os.environ.get("KAIZEN_KOTOBA_GIT_ANON", "") == "1"
        if token and not anon:
            # -c http.extraHeader injects the gate credential without writing it
            # to disk; the URL carries no secret.
            cmd = ["git", "-c", f"http.extraHeader=Authorization: Bearer {token}", *cmd[1:]]
        logger.info("kotoba git push: %s %s", remote_url, refspec)
        # No GitHub, no github.com egress — a real git-protocol push lands the
        # branch in the kotoba content-addressed Datom log on the fleet.
        subprocess.run(cmd, check=True, cwd=repo_root, capture_output=True, text=True)
        return f"kotoba:{self.repo}/refs/heads/{branch}"

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
