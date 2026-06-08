"""Resident PR-agent entry point (kaizen_pr_agent_main) — the actuator daemon
counterpart to the observer's kaizen_cell_main."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import kotodama.organism.kaizen_pr_agent_main as prmain
from kotodama.organism.kaizen.pr_agent import KaizenPrAgentAuthError


def _set_env(monkeypatch, queue: Path, repo: Path, dry_run: str = "true"):
    monkeypatch.setenv("KAIZEN_PROPOSAL_PATH", str(queue))
    monkeypatch.setenv("KAIZEN_PR_AGENT_REPO_ROOT", str(repo))
    monkeypatch.setenv("KAIZEN_PR_AGENT_DRY_RUN", dry_run)


@pytest.mark.asyncio
async def test_fire_empty_queue_consumes_nothing(tmp_path, monkeypatch):
    queue = tmp_path / "observer.ndjson"
    queue.write_text("")
    _set_env(monkeypatch, queue, tmp_path)
    with patch("subprocess.run", return_value=MagicMock(check_returncode=lambda: None, stderr="")):
        status = await prmain.fire()
    assert status["ok"] is True
    assert status["consumed"] == 0


@pytest.mark.asyncio
async def test_fire_drains_issue_only_proposal(tmp_path, monkeypatch):
    proposal = {
        "v": 1, "ts": 1, "kind": "kaizen-proposal", "ruleId": "error-rate",
        "category": "reliability", "severity": "warn", "actorScope": "shard:1",
        "summary": "error-rate issue", "detail": "...",
        "suggestedAction": {"kind": "issue-only", "description": "d",
                            "targetFiles": [], "patchHint": "", "testPlan": []},
        "prAgentHint": {"branchPrefix": "kaizen/e-", "labels": ["kaizen"]},
    }
    queue = tmp_path / "observer.ndjson"
    queue.write_text(json.dumps(proposal) + "\n")
    _set_env(monkeypatch, queue, tmp_path, dry_run="true")
    with patch("subprocess.check_output", return_value="main\n"), \
         patch("subprocess.run", return_value=MagicMock(
             check_returncode=lambda: None, stdout="", stderr="")):
        status = await prmain.fire()
    assert status["ok"] is True
    assert status["consumed"] == 1
    assert status["dryRun"] is True
    assert queue.read_text().strip() == ""  # drained


@pytest.mark.asyncio
async def test_fire_skips_cycle_when_auth_not_ready(tmp_path, monkeypatch):
    queue = tmp_path / "observer.ndjson"
    queue.write_text("{}\n")
    _set_env(monkeypatch, queue, tmp_path)
    with patch.object(prmain.KaizenPrAgent, "_verify_gh_auth",
                      side_effect=KaizenPrAgentAuthError("gh not authed")):
        status = await prmain.fire()
    assert status["ok"] is False
    assert status["reason"] == "auth"
    # Queue untouched — the daemon retries next cycle.
    assert queue.read_text().strip() == "{}"
