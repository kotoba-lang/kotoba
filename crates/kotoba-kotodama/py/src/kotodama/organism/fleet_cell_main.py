"""fleet_cell_main — UnispscOrganismFleetCell entry (lan-api trigger).

Per ADR-2605240000. Hosts N UnispscOrganism instances for a shard's
segment range, ticks all of them every ``tick_interval_s`` (default 300 s),
exposes ``/healthz`` for fleet observability.

Sharding mirrors ``UnispscAgentExecutorCell``:

  shard -1  (jacob all-segments)   segments  0-99    18,342 codes
  shard  0  (joseph)               segments 10-29     4,597 codes
  shard  1  (issachar)             segments 30-44     8,541 codes
  shard  2  (dan)                  segments 45-60     5,204 codes

Resolution order for shard index:
  1. ``UNISPSC_ORGANISM_SHARD_ALL=1`` → -1
  2. ``UNISPSC_ORGANISM_SHARD_INDEX`` int
  3. ``ETZHAYYIM_NODE`` → joseph/issachar/dan map
  4. 0
"""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

from aiohttp import web

from kotodama.organism.followers import follower_score_provider
from kotodama.organism.personality import joucho_personality_provider
from kotodama.organism.post_sink import PostSink, resolve_post_sink
from kotodama.organism.unispsc_organism import UnispscOrganism

logger = logging.getLogger("UnispscOrganismFleetCell")

REPO_ROOT = Path(__file__).resolve().parents[6]
REGISTRY_PATH = REPO_ROOT / "00-contracts" / "actor-registry" / "unispsc.json"

# Identical to UnispscAgentExecutorCell.SHARD_RANGES.
SHARD_RANGES: dict[int, tuple[int, int]] = {
    -1: (0, 99),
    0: (10, 29),
    1: (30, 44),
    2: (45, 60),
}


def _resolve_shard() -> int:
    if os.environ.get("UNISPSC_ORGANISM_SHARD_ALL", "").lower() in ("1", "true", "yes"):
        return -1
    explicit = os.environ.get("UNISPSC_ORGANISM_SHARD_INDEX")
    if explicit is not None:
        try:
            return int(explicit)
        except ValueError:
            pass
    node = os.environ.get("ETZHAYYIM_NODE") or os.environ.get("ETZHAYYIM_NODE_NAME", "")
    return {"joseph": 0, "issachar": 1, "dan": 2}.get(node, 0)


def _owns(code: str, seg_lo: int, seg_hi: int) -> bool:
    if len(code) < 2 or not code.isdigit():
        return False
    try:
        seg = int(code[:2])
    except ValueError:
        return False
    return seg_lo <= seg <= seg_hi


class OrganismCache:
    """LRU cache of UnispscOrganism instances keyed by code.

    Mirrors the shape of UnispscAgentExecutorCell.GraphCache but holds the
    full organism (CadenceState + InboxBuffer + classify graph reference)
    instead of just the compiled graph.

    A single ``post_sink`` is shared across all organisms in this cache
    so the NDJSON queue file is opened once per shard.
    """

    def __init__(self, capacity: int = 4096, *, post_sink: PostSink | None = None):
        self.capacity = max(16, capacity)
        self._d: OrderedDict[str, UnispscOrganism] = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.import_failures: dict[str, str] = {}
        self.post_sink = post_sink

    def __len__(self) -> int:
        return len(self._d)

    def get_or_create(self, code: str, title: str = "") -> UnispscOrganism | None:
        if code in self._d:
            self._d.move_to_end(code)
            self.hits += 1
            return self._d[code]
        if code in self.import_failures:
            return None
        try:
            organism = UnispscOrganism.for_code(
                code,
                title=title,
                joucho_provider=joucho_personality_provider,
                follower_score_provider=follower_score_provider,
                post_sink=self.post_sink,
            )
        except Exception as exc:  # noqa: BLE001
            self.import_failures[code] = str(exc)
            logger.warning("organism for c%s failed to import: %s", code, exc)
            return None
        self._d[code] = organism
        self._d.move_to_end(code)
        self.misses += 1
        while len(self._d) > self.capacity:
            self._d.popitem(last=False)
        return organism


class FleetState:
    def __init__(
        self,
        shard_index: int,
        *,
        organism_lru_max: int = 4096,
        post_sink: PostSink | None = None,
    ):
        self.shard_index = shard_index
        seg_lo, seg_hi = SHARD_RANGES.get(shard_index, (0, 99))
        self.seg_lo = seg_lo
        self.seg_hi = seg_hi
        self.post_sink = post_sink
        self.cache = OrganismCache(capacity=organism_lru_max, post_sink=post_sink)
        self.owned_codes: list[tuple[str, str]] = []  # (code, title)
        self.started_at = time.time()
        self.tick_count = 0
        self.last_tick_at = 0.0
        self.last_tick_duration_ms = 0.0
        self.total_posts = 0
        self.total_classifications = 0
        self.total_errors = 0

    def load_registry(self, path: Path = REGISTRY_PATH) -> None:
        with path.open("rb") as f:
            data = json.load(f)
        for row in data.get("agents", []):
            code = row.get("code")
            if not isinstance(code, str) or not _owns(code, self.seg_lo, self.seg_hi):
                continue
            title = row.get("title") or f"c{code}"
            self.owned_codes.append((code, title))
        logger.info(
            "shard-%s owns %d codes (segments %d-%d)",
            self.shard_index,
            len(self.owned_codes),
            self.seg_lo,
            self.seg_hi,
        )

    def tick_all(self, *, now_ms: int) -> None:
        """One sweep over all owned codes. Each tick is independent."""
        t0 = time.perf_counter()
        posts = 0
        classifications = 0
        errors = 0
        for code, title in self.owned_codes:
            organism = self.cache.get_or_create(code, title=title)
            if organism is None:
                errors += 1
                continue
            try:
                result = organism.tick(now_ms=now_ms)
                posts += len(result.posts)
                classifications += len(result.classifications)
            except Exception as exc:  # noqa: BLE001 — keep sweep alive
                errors += 1
                logger.warning("tick c%s failed: %s", code, exc)
        self.tick_count += 1
        self.last_tick_at = time.time()
        self.last_tick_duration_ms = (time.perf_counter() - t0) * 1000.0
        self.total_posts += posts
        self.total_classifications += classifications
        self.total_errors += errors
        logger.info(
            "shard-%s tick #%d swept %d codes in %.0f ms (posts=%d classify=%d errors=%d)",
            self.shard_index,
            self.tick_count,
            len(self.owned_codes),
            self.last_tick_duration_ms,
            posts,
            classifications,
            errors,
        )


def _bind_handlers(app: web.Application, state: FleetState) -> None:
    app["state"] = state

    async def healthz(_request: web.Request) -> web.Response:
        return web.json_response(
            {
                "ok": True,
                "service": "UnispscOrganismFleetCell",
                "shard": state.shard_index,
                "owns": f"segments {state.seg_lo}-{state.seg_hi}",
                "ownedCount": len(state.owned_codes),
                "warmCount": len(state.cache),
                "warmCapacity": state.cache.capacity,
                "hits": state.cache.hits,
                "misses": state.cache.misses,
                "tickCount": state.tick_count,
                "lastTickAt": state.last_tick_at,
                "lastTickDurationMs": round(state.last_tick_duration_ms, 2),
                "totalPosts": state.total_posts,
                "totalClassifications": state.total_classifications,
                "totalErrors": state.total_errors,
                "uptimeS": int(time.time() - state.started_at),
            }
        )

    app.router.add_get("/healthz", healthz)


async def _heartbeat_loop(state: FleetState, stop_event: asyncio.Event, tick_interval_s: int) -> None:
    """Background sweep — ticks every owned organism on cadence."""
    # Initial tick on startup so cold-start posts are emitted immediately.
    state.tick_all(now_ms=int(time.time() * 1000))
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=tick_interval_s)
            return
        except asyncio.TimeoutError:
            pass
        try:
            state.tick_all(now_ms=int(time.time() * 1000))
        except Exception as exc:  # noqa: BLE001
            logger.exception("sweep failed: %s", exc)


async def serve(stop_event: asyncio.Event, healthz_port: int, api_port: int) -> None:
    shard_index = _resolve_shard()
    lru_max = int(os.environ.get("UNISPSC_ORGANISM_LRU_MAX", "4096"))
    tick_interval_s = int(os.environ.get("UNISPSC_ORGANISM_TICK_INTERVAL_S", "300"))

    post_sink = resolve_post_sink()
    state = FleetState(shard_index, organism_lru_max=lru_max, post_sink=post_sink)
    state.load_registry()

    app = web.Application()
    _bind_handlers(app, state)

    runner = web.AppRunner(app)
    await runner.setup()
    sites = [web.TCPSite(runner, "0.0.0.0", api_port)]
    if healthz_port != api_port:
        sites.append(web.TCPSite(runner, "0.0.0.0", healthz_port))
    for site in sites:
        await site.start()

    heartbeat_task = asyncio.create_task(_heartbeat_loop(state, stop_event, tick_interval_s))

    logger.info(
        "UnispscOrganismFleetCell shard-%s serving 0.0.0.0:%d (healthz=%d) — %d owned, tick=%ds",
        state.shard_index,
        api_port,
        healthz_port,
        len(state.owned_codes),
        tick_interval_s,
    )
    try:
        await stop_event.wait()
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        await runner.cleanup()
        logger.info("UnispscOrganismFleetCell shard-%s shut down", state.shard_index)


__all__ = [
    "FleetState",
    "OrganismCache",
    "SHARD_RANGES",
    "serve",
]


# Allow `python -m kotodama.organism.fleet_cell_main` for local dev.
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _stop = asyncio.Event()
    asyncio.run(serve(_stop, healthz_port=13040, api_port=13040))
