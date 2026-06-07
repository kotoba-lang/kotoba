"""
UnispscAgentExecutorCell — LAN HTTP service that invokes per-actor LangGraph
StateGraphs for the 18,342 UNSPSC commodity agents.

Per ADR-2605171300 + ADR-2605192415 §4 (sharded across joseph/issachar/dan).
Each shard owns a contiguous segment-prefix range:

  shard-0  joseph    segments 10-29  (~4,260 agents)
  shard-1  issachar  segments 30-44  (~8,800 agents)  ← heaviest
  shard-2  dan       segments 45-60  (~5,280 agents)

The cell:
  - Validates incoming `code` against an in-memory registry copy
  - Confirms `code`'s segment falls inside this shard's range (else 421 misroute)
  - Lazily imports ``kotodama.langgraph_graphs.unispsc_agents.c{code}``
  - LRU-caches the compiled StateGraph (capacity = ``warm_lru_max``, default 4096)
  - Invokes ``graph.invoke(input)`` and returns the terminal state as JSON

Endpoints (POST unless noted):
  GET  /healthz                 → {ok, shard, owns, warmCount, ...}
  POST /api/invoke              → {code, input?, threadId?} → {ok, code, state, latencyMs}
  POST /api/invokeAgent         → alias of /api/invoke (xrpc shape)

Trigger kind: ``lan-api`` (custom — see cell_runner_main._spawn_lan_api_cell).
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
from typing import Any, Callable

from aiohttp import web

from kotodama.checkpointer.mst_saver import (
    MstCheckpointSaver,
    MstCheckpointSaverError,
)

logger = logging.getLogger("UnispscAgentExecutorCell")

REPO_ROOT = Path(__file__).resolve().parents[4]
REGISTRY_PATH = REPO_ROOT / "00-contracts" / "actor-registry" / "unispsc.json"
AGENTS_PKG = "kotodama.langgraph_graphs.unispsc_agents"

# Shard topology — matches fleet.toml [cells.UnispscAgentExecutorCell.shard_assignments].
# Index -1 is a synthetic "all-segments" mode (jacob single-node operation,
# per the 2026-05-23 ops decision to run all 18,342 actors on one host while
# the 3-mac-mini fleet shard rollout is pending).
SHARD_RANGES: dict[int, tuple[int, int]] = {
    -1: (0, 99),   # ALL — jacob single-node
    0: (10, 29),   # joseph
    1: (30, 44),   # issachar
    2: (45, 60),   # dan
}

GraphTransform = Callable[[Any, str], Any]


class GraphCache:
    """LRU cache of compiled StateGraphs keyed by unispsc code.

    If ``transform`` is set, it is called once per import with
    ``transform(graph, code)`` and its return value is stored in place of the
    raw module-level ``graph``. This is the injection point for the
    MstCheckpointSaver rebind (per ADR-2605171800 Stage 1–2) — the bound
    graph is what subsequent LRU hits return, so we recompile once per code,
    not once per invoke.
    """

    def __init__(
        self,
        capacity: int = 4096,
        transform: GraphTransform | None = None,
    ):
        self.capacity = max(16, capacity)
        self._d: OrderedDict[str, Any] = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.import_failures: dict[str, str] = {}
        self.transform = transform

    def __len__(self) -> int:
        return len(self._d)

    def get_or_load(self, code: str) -> Any | None:
        if code in self._d:
            self._d.move_to_end(code)
            self.hits += 1
            return self._d[code]
        if code in self.import_failures:
            return None
        try:
            mod = importlib.import_module(f"{AGENTS_PKG}.c{code}")
        except Exception as exc:  # noqa: BLE001
            logger.warning("import c%s failed: %s", code, exc)
            self.import_failures[code] = str(exc)
            return None
        graph = getattr(mod, "graph", None)
        if graph is None:
            self.import_failures[code] = "module has no `graph` attribute"
            return None
        if self.transform is not None:
            try:
                graph = self.transform(graph, code)
            except Exception as exc:  # noqa: BLE001
                logger.warning("transform c%s failed: %s", code, exc)
                self.import_failures[code] = f"transform: {exc}"
                return None
        self._d[code] = graph
        self._d.move_to_end(code)
        self.misses += 1
        while len(self._d) > self.capacity:
            self._d.popitem(last=False)
        return graph


class ShardState:
    def __init__(
        self,
        shard_index: int,
        capacity: int = 4096,
        checkpointer_socket: str | None = None,
    ):
        self.shard_index = shard_index
        seg_lo, seg_hi = SHARD_RANGES.get(shard_index, (0, 99))
        self.seg_lo = seg_lo
        self.seg_hi = seg_hi
        self.valid_codes: set[str] = set()
        self.code_to_did: dict[str, str] = {}
        self.started_at = time.time()
        self.last_invoke_at: float = 0.0
        self.invoke_count = 0
        self.invoke_errors = 0

        # Per-cell_did saver pool. Saver construction is cheap (lazy socket)
        # so we create on demand and keep one per actor DID. The socket only
        # opens when the saver is first asked to put/get.
        self.checkpointer_socket = checkpointer_socket
        self.saver_cache: dict[str, MstCheckpointSaver] = {}
        self.saver_init_failures: dict[str, str] = {}
        self.rebind_failures: dict[str, str] = {}
        self.rebound_count = 0
        self.plaintext_count = 0  # graphs that fell back to unbound (no .builder)

        transform = self._make_transform() if checkpointer_socket else None
        self.cache = GraphCache(capacity=capacity, transform=transform)

    def owns(self, code: str) -> bool:
        if len(code) < 2 or not code.isdigit():
            return False
        try:
            seg = int(code[:2])
        except ValueError:
            return False
        return self.seg_lo <= seg <= self.seg_hi

    def load_registry(self, path: Path = REGISTRY_PATH) -> None:
        with path.open("rb") as f:
            data = json.load(f)
        for row in data.get("agents", []):
            code = row.get("code")
            if not code or not self.owns(code):
                continue
            self.valid_codes.add(code)
            did = row.get("did")
            if isinstance(did, str) and did.startswith("did:"):
                self.code_to_did[code] = did
        logger.info(
            "shard-%s loaded %d codes / %d DIDs (segments %d-%d) checkpointer=%s",
            self.shard_index,
            len(self.valid_codes),
            len(self.code_to_did),
            self.seg_lo,
            self.seg_hi,
            self.checkpointer_socket or "DISABLED",
        )

    # ── checkpointer binding ────────────────────────────────────────────

    def _make_transform(self) -> GraphTransform:
        def _bind(graph: Any, code: str) -> Any:
            did = self.code_to_did.get(code)
            if not did:
                # No DID in registry → leave graph unbound. Invoke still works,
                # just without checkpoint persistence for this code.
                self.plaintext_count += 1
                return graph
            builder = getattr(graph, "builder", None)
            if builder is None:
                self.plaintext_count += 1
                self.rebind_failures[code] = "compiled graph has no .builder"
                return graph
            saver = self.saver_cache.get(did)
            if saver is None:
                try:
                    saver = MstCheckpointSaver(
                        cell_did=did,
                        socket_path=self.checkpointer_socket,  # type: ignore[arg-type]
                    )
                except Exception as exc:  # noqa: BLE001
                    self.saver_init_failures[did] = str(exc)
                    self.plaintext_count += 1
                    return graph
                self.saver_cache[did] = saver
            try:
                rebound = builder.compile(checkpointer=saver)
            except Exception as exc:  # noqa: BLE001
                self.rebind_failures[code] = str(exc)
                self.plaintext_count += 1
                return graph
            self.rebound_count += 1
            return rebound

        return _bind


# ── HTTP handlers ───────────────────────────────────────────────────────


def _bind_handlers(app: web.Application, shard: ShardState) -> None:
    app["shard"] = shard

    async def healthz(_request: web.Request) -> web.Response:
        return web.json_response({
            "ok": True,
            "service": "UnispscAgentExecutorCell",
            "shard": shard.shard_index,
            "owns": f"segments {shard.seg_lo}-{shard.seg_hi}",
            "validCodeCount": len(shard.valid_codes),
            "didCount": len(shard.code_to_did),
            "warmCount": len(shard.cache),
            "warmCapacity": shard.cache.capacity,
            "hits": shard.cache.hits,
            "misses": shard.cache.misses,
            "invokeCount": shard.invoke_count,
            "invokeErrors": shard.invoke_errors,
            "checkpointer": {
                "socket": shard.checkpointer_socket,
                "enabled": shard.checkpointer_socket is not None,
                "saverCount": len(shard.saver_cache),
                "reboundCount": shard.rebound_count,
                "plaintextCount": shard.plaintext_count,
                "rebindFailureCount": len(shard.rebind_failures),
                "saverInitFailureCount": len(shard.saver_init_failures),
            },
            "uptimeS": int(time.time() - shard.started_at),
        })

    async def invoke(request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return web.json_response(
                {"ok": False, "error": "InvalidJSON"}, status=400
            )
        code = str(body.get("code") or "")
        if not code:
            return web.json_response(
                {"ok": False, "error": "CodeRequired"}, status=400
            )
        if not shard.owns(code):
            return web.json_response(
                {
                    "ok": False,
                    "error": "Misrouted",
                    "code": code,
                    "shard": shard.shard_index,
                    "owns": f"{shard.seg_lo}-{shard.seg_hi}",
                },
                status=421,
            )
        if code not in shard.valid_codes:
            return web.json_response(
                {"ok": False, "error": "AgentNotFound", "code": code},
                status=404,
            )
        graph = shard.cache.get_or_load(code)
        if graph is None:
            shard.invoke_errors += 1
            return web.json_response(
                {
                    "ok": False,
                    "error": "ImportFailed",
                    "code": code,
                    "detail": shard.cache.import_failures.get(code, "unknown"),
                },
                status=500,
            )
        input_state = body.get("input") or body.get("state") or {}
        if not isinstance(input_state, dict):
            return web.json_response(
                {"ok": False, "error": "InputMustBeObject"}, status=400
            )
        thread_id = str(body.get("threadId") or f"unispsc-{code}-{int(time.time() * 1000)}")
        checkpoint_ns = str(body.get("checkpointNs") or "")
        config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
            }
        }
        t0 = time.perf_counter()
        try:
            # graph.invoke is sync — run in default executor to avoid blocking
            # the event loop on long-running StateGraph traversals.
            loop = asyncio.get_running_loop()
            terminal = await loop.run_in_executor(
                None, lambda: graph.invoke(input_state, config=config)
            )
        except MstCheckpointSaverError as exc:
            shard.invoke_errors += 1
            logger.warning("invoke c%s checkpointer failed: %s", code, exc)
            return web.json_response(
                {
                    "ok": False,
                    "error": "CheckpointerError",
                    "code": code,
                    "detail": str(exc),
                },
                status=502,
            )
        except Exception as exc:  # noqa: BLE001 — surface as 500
            shard.invoke_errors += 1
            logger.exception("invoke c%s failed", code)
            return web.json_response(
                {
                    "ok": False,
                    "error": "InvokeException",
                    "code": code,
                    "detail": str(exc),
                },
                status=500,
            )
        finally:
            shard.invoke_count += 1
            shard.last_invoke_at = time.time()
        latency_ms = (time.perf_counter() - t0) * 1000
        return web.json_response({
            "ok": True,
            "code": code,
            "shard": shard.shard_index,
            "threadId": thread_id,
            "state": terminal if isinstance(terminal, dict) else {"value": terminal},
            "latencyMs": round(latency_ms, 2),
        })

    app.router.add_get("/healthz", healthz)
    app.router.add_post("/api/invoke", invoke)
    app.router.add_post("/api/invokeAgent", invoke)


# ── cell-runner contract ────────────────────────────────────────────────


def healthz() -> dict[str, Any]:
    return {"ok": True, "service": "UnispscAgentExecutorCell"}


def _resolve_shard() -> int:
    """Resolve shard index from env → fleet.toml mapping.

    UNISPSC_SHARD_ALL=1 selects synthetic shard -1 (all segments 0-99), used
    when running every actor on a single host (jacob). UNISPSC_SHARD_INDEX
    takes precedence and accepts -1/0/1/2. Falls back to ETZHAYYIM_NODE
    name → joseph/issachar/dan mapping, else 0.
    """
    if os.environ.get("UNISPSC_SHARD_ALL", "").lower() in ("1", "true", "yes"):
        return -1
    explicit = os.environ.get("UNISPSC_SHARD_INDEX")
    if explicit is not None:
        try:
            return int(explicit)
        except ValueError:
            pass
    node = os.environ.get("ETZHAYYIM_NODE") or os.environ.get(
        "ETZHAYYIM_NODE_NAME", ""
    )
    return {"joseph": 0, "issachar": 1, "dan": 2}.get(node, 0)


async def serve(stop_event: asyncio.Event, healthz_port: int, api_port: int) -> None:
    shard_index = _resolve_shard()
    capacity = int(os.environ.get("UNISPSC_WARM_LRU_MAX", "4096"))
    checkpointer_socket = os.environ.get("ETZ_CHECKPOINTER_SOCKET") or None
    shard = ShardState(
        shard_index,
        capacity=capacity,
        checkpointer_socket=checkpointer_socket,
    )
    shard.load_registry()

    app = web.Application()
    _bind_handlers(app, shard)

    runner = web.AppRunner(app)
    await runner.setup()
    sites = [web.TCPSite(runner, "0.0.0.0", api_port)]
    if healthz_port != api_port:
        sites.append(web.TCPSite(runner, "0.0.0.0", healthz_port))
    for site in sites:
        await site.start()
    logger.info(
        "UnispscAgentExecutorCell shard-%s serving 0.0.0.0:%d (healthz=%d) — %d codes",
        shard.shard_index,
        api_port,
        healthz_port,
        len(shard.valid_codes),
    )
    try:
        await stop_event.wait()
    finally:
        await runner.cleanup()
        logger.info("UnispscAgentExecutorCell shard-%s shut down", shard.shard_index)


__all__ = ["ShardState", "GraphCache", "SHARD_RANGES", "healthz", "serve"]
