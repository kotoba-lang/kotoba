"""kaizen_pr_agent_main — resident entry for the Kaizen PR-agent actuator.

The counterpart to ``kaizen_cell_main`` (the observer). The observer writes
KaizenProposal NDJSON lines to a shared queue; this resident process drains
that queue, applies structured patches, and opens GitHub PRs / issues —
closing the self-evolution loop.

Deployment (per ADR-2605240200 Wave 4): runs on the Murakumo Mac mini fleet as
a resident Deployment (sibling of the ``kaizen-observer`` Deployment on levi),
reading the SAME ``/var/lib/etzhayyim/kaizen-proposals/observer.ndjson`` volume
the observer writes.

Configuration via env vars:
  - ``KAIZEN_PROPOSAL_PATH``        proposal queue NDJSON (default matches the
                                    observer's output path).
  - ``KAIZEN_PR_AGENT_REPO_ROOT``   checkout the PR agent operates on (the
                                    etzhayyim/root working tree).
  - ``KAIZEN_PR_AGENT_INTERVAL_S``  poll cadence when running standalone
                                    (default 600 = 10 min).
  - ``KAIZEN_PR_AGENT_DRY_RUN``     "true" (default, safe) → patches applied to
                                    the local checkout + ``gh ... --dry-run``;
                                    "false" → actually opens PRs/issues.
  - ``KAIZEN_PR_AGENT_LOG_LEVEL``   stdlib level name (default "INFO").

no-server-key note (ADR-2605231525): opening real PRs requires GitHub write
auth. This process is operator-credentialed (a short-lived token injected at
runtime), NOT a platform-held master key, and the default is dry-run so a pod
that starts without a token drains-and-patches locally without pushing.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from kotodama.organism.kaizen.pr_agent import KaizenPrAgent, KaizenPrAgentAuthError

logger = logging.getLogger("kotodama.organism.kaizen_pr_agent")


def _default_proposal_path() -> Path:
    explicit = os.environ.get("KAIZEN_PROPOSAL_PATH")
    if explicit:
        return Path(explicit)
    base = os.environ.get("KAIZEN_PROPOSAL_BASE", "/var/lib/etzhayyim/kaizen-proposals")
    return Path(base) / "observer.ndjson"


def _repo_root() -> Path:
    return Path(os.environ.get("KAIZEN_PR_AGENT_REPO_ROOT", os.getcwd()))


def _dry_run() -> bool:
    return os.environ.get("KAIZEN_PR_AGENT_DRY_RUN", "true").lower() not in ("0", "false", "no")


async def fire() -> dict[str, Any]:
    """One drain pass over the proposal queue. Returns a status dict.

    Constructs the agent per cycle so a missing/expired GitHub credential is a
    skipped cycle (logged), not a crashed daemon — the resident loop survives
    until auth is configured.
    """
    proposal_path = _default_proposal_path()
    repo_root = _repo_root()
    dry_run = _dry_run()

    loop = asyncio.get_running_loop()

    def _drain() -> dict[str, Any]:
        try:
            agent = KaizenPrAgent(proposal_path, repo_root, dry_run=dry_run)
        except KaizenPrAgentAuthError as exc:
            logger.warning("PR agent auth not ready — skipping cycle: %s", exc)
            return {"ok": False, "reason": "auth", "consumed": 0, "urls": []}
        if not proposal_path.exists() or proposal_path.stat().st_size == 0:
            return {"ok": True, "consumed": 0, "urls": [], "dryRun": dry_run}
        urls = agent.consume_all()
        return {"ok": True, "consumed": len(urls), "urls": urls, "dryRun": dry_run}

    status = await loop.run_in_executor(None, _drain)
    logger.info(
        "pr-agent drain: consumed=%d dryRun=%s proposalPath=%s",
        status.get("consumed", 0), dry_run, proposal_path,
    )
    return status


async def serve_loop() -> None:
    """Resident loop. k8s Deployment entrypoint on the Mac mini fleet."""
    interval_s = int(os.environ.get("KAIZEN_PR_AGENT_INTERVAL_S", "600"))
    logger.info(
        "kaizen-pr-agent resident loop start: interval=%ds repo_root=%s dry_run=%s",
        interval_s, _repo_root(), _dry_run(),
    )
    while True:
        try:
            await fire()
        except Exception as exc:  # noqa: BLE001 — resident loop must survive a bad cycle
            logger.exception("pr-agent cycle failed (continuing): %s", exc)
        await asyncio.sleep(interval_s)


__all__ = ["fire", "serve_loop"]


if __name__ == "__main__":
    logging.basicConfig(
        level=getattr(logging, os.environ.get("KAIZEN_PR_AGENT_LOG_LEVEL", "INFO").upper(), logging.INFO)
    )
    asyncio.run(serve_loop())
