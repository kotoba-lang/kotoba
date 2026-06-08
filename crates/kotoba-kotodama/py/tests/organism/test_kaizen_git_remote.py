"""Tests for the pluggable GitRemote (GitHub vs kotoba) of the Kaizen actuator.

Guards the GitHub-independence path: with KAIZEN_GIT_REMOTE=kotoba the loop
publishes a committed branch into kotoba's content-addressed Datom store via the
`kotoba git import` write surface — no `gh`, no github.com egress.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from kotodama.organism.kaizen.git_remote import (
    GithubRemote,
    KotobaRemote,
    select_remote,
)


def test_select_remote_default_is_github(monkeypatch):
    monkeypatch.delenv("KAIZEN_GIT_REMOTE", raising=False)
    assert select_remote().name == "github"


def test_select_remote_kotoba_by_env(monkeypatch):
    monkeypatch.setenv("KAIZEN_GIT_REMOTE", "kotoba")
    assert select_remote().name == "kotoba"


def test_select_remote_explicit_name_overrides_env(monkeypatch):
    monkeypatch.setenv("KAIZEN_GIT_REMOTE", "kotoba")
    assert select_remote("github").name == "github"


@patch("subprocess.run")
def test_github_open_change_pushes_and_opens_pr(mock_run):
    pr_url = "https://github.com/etzhayyim/root/pull/9"
    mock_run.return_value = MagicMock(stdout=pr_url, text=True)
    out = GithubRemote().open_change(
        repo_root=Path("/repo"), branch="kaizen/x", title="t", body="b", labels=["kaizen"]
    )
    assert out == pr_url
    flat = [c.args[0] for c in mock_run.call_args_list]
    assert ["gh", "auth", "setup-git"] in flat
    assert any(cmd[:2] == ["git", "push"] for cmd in flat)
    gh = [cmd for cmd in flat if cmd[:3] == ["gh", "pr", "create"]]
    assert gh and "--head" in gh[0] and "--label" in gh[0]


@patch("subprocess.run")
def test_github_change_state_maps_merged(mock_run):
    mock_run.return_value = MagicMock(stdout="MERGED\n")
    assert GithubRemote().change_state("kaizen/x", repo_root=Path("/repo")) == "merged"


@patch("subprocess.run")
def test_kotoba_open_change_shells_kotoba_import_no_github(mock_run, monkeypatch):
    monkeypatch.setenv("KAIZEN_KOTOBA_GIT_CMD", "kotoba git import")
    monkeypatch.setenv("KAIZEN_KOTOBA_GRAPH", "kaizen:self-evolution")
    mock_run.return_value = MagicMock(stdout="", text=True)
    out = KotobaRemote().open_change(
        repo_root=Path("/repo"), branch="kaizen/x", title="t", body="b", labels=[]
    )
    assert out == "kotoba:kaizen:self-evolution/refs/heads/kaizen/x"
    flat = [c.args[0] for c in mock_run.call_args_list]
    # Exactly one shell-out: the kotoba import. No `gh`, no `git push`.
    assert len(flat) == 1
    cmd = flat[0]
    assert cmd[:3] == ["kotoba", "git", "import"]
    assert "/repo/.git" in cmd
    assert "--graph" in cmd and "kaizen:self-evolution" in cmd
    assert "--ref" in cmd and "refs/heads/kaizen/x" in cmd
    assert not any("gh" == part for part in cmd)


@patch("subprocess.run")
def test_kotoba_change_state_env_markers(mock_run, monkeypatch):
    ref = "kotoba:kaizen:self-evolution/refs/heads/kaizen/x"
    # Default: pending (open) — no GitHub call made.
    monkeypatch.delenv("KAIZEN_KOTOBA_APPROVED_REFS", raising=False)
    monkeypatch.delenv("KAIZEN_KOTOBA_REJECTED_REFS", raising=False)
    r = KotobaRemote()
    assert r.change_state(ref, repo_root=Path("/repo")) == "open"
    monkeypatch.setenv("KAIZEN_KOTOBA_APPROVED_REFS", ref)
    assert r.change_state(ref, repo_root=Path("/repo")) == "merged"
    monkeypatch.setenv("KAIZEN_KOTOBA_APPROVED_REFS", "")
    monkeypatch.setenv("KAIZEN_KOTOBA_REJECTED_REFS", ref)
    assert r.change_state(ref, repo_root=Path("/repo")) == "closed"
    # kotoba state resolution must never call out to github.
    mock_run.assert_not_called()


@patch("subprocess.run")
def test_pr_agent_kotoba_remote_needs_no_gh_auth(mock_run, tmp_path):
    """A KotobaRemote-backed agent must construct without `gh auth status`."""
    from kotodama.organism.kaizen.pr_agent import KaizenPrAgent

    q = tmp_path / "q.ndjson"
    q.write_text("")
    repo = tmp_path / "repo"
    repo.mkdir()
    KaizenPrAgent(q, repo, dry_run=False, remote=KotobaRemote())
    # No subprocess at all during construction (GithubRemote would `gh auth status`).
    mock_run.assert_not_called()
