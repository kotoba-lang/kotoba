"""Follower-score provider for the Python organism path.

Per ADR-2605240030. Interface only — real AT Protocol read lands in a
follow-up ADR once the ``@etzhayyim/sdk`` Python binding is available.

Three providers:
  - ``follower_score_provider``: default stub, returns [].
  - ``file_follower_score_provider(path)``: reads a JSON seed file
    keyed by actor DID. For tests + local-dev.
  - ``MstFollowerScoreProvider`` (Protocol): forward-compat interface
    for the future AT Protocol implementation.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Callable, Protocol

from kotodama.organism.inbox import FollowerCurrentScore

logger = logging.getLogger("kotodama.organism.followers")


def follower_score_provider(actor_did: str) -> list[FollowerCurrentScore]:
    """Default stub — returns no followers.

    Real implementation deferred to Wave 3 (AT Protocol read via
    ``@etzhayyim/sdk`` Python binding).
    """
    seed_path = os.environ.get("UNISPSC_ORGANISM_FOLLOWER_SEED")
    if seed_path:
        return _file_provider_singleton(seed_path)(actor_did)
    return []


def _coerce_follower_row(row: dict) -> FollowerCurrentScore | None:
    did = row.get("did") or row.get("actorDid")
    if not isinstance(did, str) or not did:
        return None
    return FollowerCurrentScore(
        did=did,
        wellness_score=float(row.get("wellnessScore", row.get("wellness_score", 0)) or 0),
        dojo_score=float(row.get("dojoScore", row.get("dojo_score", 0)) or 0),
        rank=str(row.get("rank") or "kyu6"),
        latest_post_uri=row.get("latestPostUri") or row.get("latest_post_uri") or None,
    )


def file_follower_score_provider(path: str | Path) -> Callable[[str], list[FollowerCurrentScore]]:
    """Build a provider that reads followers from a JSON file.

    File format::

        {
          "did:web:etzhayyim.com:actor:c10101500": [
            { "did": "did:...", "wellnessScore": 50, "dojoScore": 0, "rank": "kyu6" }
          ]
        }

    The file is loaded once at provider construction; subsequent reads
    return cached rows. Missing actor DIDs return [].
    """
    cache: dict[str, list[FollowerCurrentScore]] = {}
    p = Path(path)
    try:
        with p.open("rb") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            for actor_did, rows in raw.items():
                if not isinstance(actor_did, str) or not isinstance(rows, list):
                    continue
                coerced: list[FollowerCurrentScore] = []
                for r in rows:
                    if isinstance(r, dict):
                        item = _coerce_follower_row(r)
                        if item is not None:
                            coerced.append(item)
                cache[actor_did] = coerced
    except FileNotFoundError:
        logger.warning("follower seed file not found: %s", p)
    except Exception as exc:  # noqa: BLE001
        logger.warning("follower seed file %s failed to parse: %s", p, exc)

    def provider(actor_did: str) -> list[FollowerCurrentScore]:
        return list(cache.get(actor_did, []))

    return provider


_file_provider_cache: dict[str, Callable[[str], list[FollowerCurrentScore]]] = {}


def _file_provider_singleton(path: str) -> Callable[[str], list[FollowerCurrentScore]]:
    if path not in _file_provider_cache:
        _file_provider_cache[path] = file_follower_score_provider(path)
    return _file_provider_cache[path]


# ── Future hook (ADR-2605240030 Wave 3, deferred) ─────────────────────


class MstFollowerScoreProvider(Protocol):
    """Forward-compat interface for the future AT Protocol implementation.

    Wave 3 will provide a class that reads follow edges via
    ``@etzhayyim/sdk`` Python binding and joins them against the
    ``com.etzhayyim.apps.etzhayyim.joucho.score`` MST collection (ADR-2605240015
    Layer 2) for wellness / dojo data.
    """

    def __call__(self, actor_did: str) -> list[FollowerCurrentScore]:  # pragma: no cover
        ...


__all__ = [
    "MstFollowerScoreProvider",
    "file_follower_score_provider",
    "follower_score_provider",
]
