"""cell_main — cron-trigger entry for UNSPSC organism cells.

Per ADR-2605232345. The cell-runner cron path calls ``await fire()`` every
heartbeat tick (default 5 min). Each invocation:

  1. Lazy-imports the underlying UNSPSC LangGraph from ``c{code}``.
  2. Builds the organism wrapper (cached across ticks via module global).
  3. Calls ``organism.tick(now_ms=...)``.
  4. Logs cadence + classifications + posts.

Configuration via env vars:
  - ``UNISPSC_ORGANISM_CODE``: 8-digit code (default "10101500").
  - ``UNISPSC_ORGANISM_LOG_LEVEL``: stdlib level name (default "INFO").
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from kotodama.organism.inbox import InboundCommit
from kotodama.organism.lifecycle import OrganismState
from kotodama.organism.post_sink import resolve_post_sink
from kotodama.organism.organism import Organism

logger = logging.getLogger("kotodama.organism.cell_main")

_organism: Organism | None = None


def _resolve_code() -> str:
    return os.environ.get("UNISPSC_ORGANISM_CODE", "10101500")


def _build_organism() -> Organism:
    """Build the reference organism with the env-resolved post sink.

    UNISPSC_ORGANISM_POST_SINK=ndjson activates the substrate-bound NDJSON
    queue sink (ADR-2605240100); default ``logger`` writes to stdout.
    """
    return Organism.for_code(_resolve_code(), post_sink=resolve_post_sink())


def _ensure_organism() -> Organism:
    global _organism
    if _organism is None:
        level = os.environ.get("UNISPSC_ORGANISM_LOG_LEVEL", "INFO").upper()
        logging.basicConfig(level=getattr(logging, level, logging.INFO))
        _organism = _build_organism()
        # Birth the organism so its lifecycle is ACTIVE — without this the
        # tick gate (Organism.tick early-returns a no-op dummy cadence
        # while the lifecycle is INACTIVE) would make a fired cell never post.
        # The cell-runner firing a cell IS the spawn event in production.
        if _organism.lifecycle.state is OrganismState.INACTIVE:
            _organism.lifecycle.handle_birth(_organism.actor_did)
        logger.info(
            "organism initialized: code=%s did=%s title=%s state=%s",
            _organism.code,
            _organism.actor_did,
            _organism.title,
            _organism.lifecycle.state.value,
        )
    return _organism


def _seed_self_inbox(organism: Organism, now_ms: int) -> None:
    """Until MST subscription is wired (ADR-2605232345 §Phase 6), seed one
    synthetic inbound commit per tick so the heartbeat exercises the
    classify path. Real deployment replaces this with MST listener pushes.
    """
    rkey = f"selfprobe-{now_ms}"
    organism.inbox.add_commit(
        InboundCommit(
            collection="com.etzhayyim.apps.unispsc.invokeAgent",
            repo=organism.actor_did,
            rkey=rkey,
            time=str(now_ms),
        )
    )


async def fire() -> dict[str, Any]:
    """Cron-trigger entry. Returns a small status dict for logging/tests."""
    organism = _ensure_organism()
    now_ms = int(time.time() * 1000)
    _seed_self_inbox(organism, now_ms)
    result = organism.tick(now_ms=now_ms)
    logger.info(
        "tick #%d cadence=%s posts=%d classifications=%d rewards=%d",
        organism.tick_count,
        result.cadence.reason,
        len(result.posts),
        len(result.classifications),
        len(result.rewards),
    )
    return {
        "code": organism.code,
        "tickCount": organism.tick_count,
        "mood": result.cadence.mood,
        "shouldPost": result.cadence.should_post,
        "contentSource": result.cadence.content_source.kind,
        "posts": result.posts,
        "classifications": result.classifications,
        "rewards": [
            {"did": r.did, "metric": r.metric, "reward": r.reward_type}
            for r in result.rewards
        ],
    }


__all__ = ["fire"]
