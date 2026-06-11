"""kaizen_cell_main — cron-trigger entry for KaizenObserverCell.

Per ADR-2605240200. Probes shard healthz + queue tails, runs rules,
appends KaizenProposal NDJSON lines to the proposal queue.

Configuration via env vars:
  - ``KAIZEN_SHARD_URLS``      comma-separated; default in-cluster Service DNS
  - ``KAIZEN_QUEUE_PATHS``     comma-separated NDJSON files
  - ``KAIZEN_PROPOSAL_PATH``   default /var/lib/etzhayyim/kaizen-proposals/observer.ndjson
  - ``KAIZEN_TICK_INTERVAL_S`` (only used when running standalone)
  - ``KAIZEN_DEDUP_WINDOW_S``  default 7200
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any

from kotodama.organism.kaizen import KaizenObserver

logger = logging.getLogger("kotodama.organism.kaizen_cell_main")

_observer: KaizenObserver | None = None


def _default_shard_urls() -> list[str]:
    explicit = os.environ.get("KAIZEN_SHARD_URLS")
    if explicit:
        return [u.strip() for u in explicit.split(",") if u.strip()]
    return [
        "http://unispsc-organism-fleet-shard-0.etzhayyim-organism.svc:13040",
        "http://unispsc-organism-fleet-shard-1.etzhayyim-organism.svc:13050",
        "http://unispsc-organism-fleet-shard-2.etzhayyim-organism.svc:13060",
    ]


def _default_queue_paths() -> list[Path]:
    explicit = os.environ.get("KAIZEN_QUEUE_PATHS")
    if explicit:
        return [Path(p) for p in explicit.split(",") if p.strip()]
    base = Path(os.environ.get("KAIZEN_QUEUE_BASE", "/var/lib/etzhayyim/organism-posts"))
    return [base / f"shard-{i}.ndjson" for i in range(3)]


def _default_proposal_path() -> Path:
    explicit = os.environ.get("KAIZEN_PROPOSAL_PATH")
    if explicit:
        return Path(explicit)
    base = Path("/var/lib/etzhayyim/kaizen-proposals")
    if base.parent.is_dir() and os.access(base.parent, os.W_OK):
        return base / "observer.ndjson"
    home = Path.home() / ".etzhayyim" / "log" / "kaizen-proposals"
    return home / "observer.ndjson"


def _fitness_path() -> Path:
    explicit = os.environ.get("KAIZEN_FITNESS_PATH")
    if explicit:
        return Path(explicit)
    # Sibling of the proposal queue (same shared hostPath the pr-agent updates).
    pp = _default_proposal_path()
    return pp.parent / "rule-fitness.json"


def _build_observer() -> KaizenObserver:
    # Meta self-reflection: prune rules whose PRs humans keep rejecting. The
    # pr-agent resolves PR outcomes into this ledger; the observer reads it to
    # skip pruned rules. Disabled with KAIZEN_META_REFLECT=0.
    meta_reflector = None
    if os.environ.get("KAIZEN_META_REFLECT", "1").lower() not in ("0", "false", "no"):
        from kotodama.organism.kaizen.fitness import RuleFitnessLedger, MetaReflector
        ledger = RuleFitnessLedger(_fitness_path())
        meta_reflector = MetaReflector(
            ledger,
            min_samples=int(os.environ.get("KAIZEN_PRUNE_MIN_SAMPLES", "5")),
            prune_below=float(os.environ.get("KAIZEN_PRUNE_BELOW", "0.34")),
        )
    return KaizenObserver(
        shard_urls=_default_shard_urls(),
        queue_paths=_default_queue_paths(),
        proposal_path=_default_proposal_path(),
        dedup_window_s=int(os.environ.get("KAIZEN_DEDUP_WINDOW_S", "7200")),
        meta_reflector=meta_reflector,
    )


def _ensure_observer() -> KaizenObserver:
    global _observer
    if _observer is None:
        level = os.environ.get("KAIZEN_LOG_LEVEL", "INFO").upper()
        logging.basicConfig(level=getattr(logging, level, logging.INFO))
        _observer = _build_observer()
        logger.info(
            "kaizen-observer initialized: shards=%d queues=%d proposal_path=%s",
            len(_observer.shard_urls),
            len(_observer.queue_paths),
            _observer.proposal_path,
        )
    return _observer


async def fire() -> dict[str, Any]:
    """Cron-trigger entry. Returns observer status."""
    observer = _ensure_observer()
    # urllib.request blocks; run probe in default executor.
    loop = asyncio.get_running_loop()
    status = await loop.run_in_executor(None, observer.tick)
    logger.info(
        "kaizen tick #%d reachable=%d/%d raised=%d kept=%d written=%d",
        observer.tick_count,
        status["reachable"],
        status["shardCount"],
        status["proposalsRaised"],
        status["proposalsAfterDedup"],
        status["proposalsWritten"],
    )
    return status


async def serve_loop() -> None:
    """Standalone loop. For local dev — k8s uses cron-cell wrapper."""
    interval_s = int(os.environ.get("KAIZEN_TICK_INTERVAL_S", "600"))
    while True:
        await fire()
        await asyncio.sleep(interval_s)


__all__ = ["fire", "serve_loop"]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(serve_loop())
