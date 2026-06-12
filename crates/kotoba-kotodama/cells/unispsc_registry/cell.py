"""
UnispscRegistryCell — LAN HTTP service for the 18,342 UNSPSC actor registry.

Per ADR-2605171300 (UNSPSC 18k actors) + ADR-2605192415 §4 (Pregel cell catalog,
asher node assignment). Read-only mirror of the bundled XRPC façade
(yoro-xrpc-adapter); serves listAgents / health to in-fleet callers and is
the dispatch source-of-truth that UnispscAgentExecutorCell consults to
validate codes before invoking the per-actor StateGraph.

Trigger kind: ``lan-api`` (custom — see cell_runner_main._spawn_lan_api_cell).
The cell exposes both /healthz (port 13023) and /api/* (port 13123) on the
loopback interface; cell-runner inspects fleet.toml to derive both ports.

Endpoints (all GET):
  /healthz              → {ok, agentCount, generatedAt}
  /api/listAgents       → {agents, totalCount, cursor?}
  /api/agent/{code}     → {code, handle, title, segment, did} or 404
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from aiohttp import web

logger = logging.getLogger("UnispscRegistryCell")

REPO_ROOT = Path(__file__).resolve().parents[4]
REGISTRY_PATH = REPO_ROOT / "00-contracts" / "actor-registry" / "unispsc.json"
DID_ENTITY = "did:web:etzhayyim.com"


class Registry:
    """In-memory immutable view of unispsc.json."""

    def __init__(self, path: Path):
        self.path = path
        self.generated_at: str = ""
        self.total: int = 0
        self.agents: list[dict[str, Any]] = []
        self._by_code: dict[str, int] = {}
        self.loaded_at: float = 0.0

    def load(self) -> None:
        with self.path.open("rb") as f:
            data = json.load(f)
        self.generated_at = data.get("generatedAt", "")
        self.agents = data.get("agents", [])
        self.total = data.get("totalCount", len(self.agents))
        self._by_code = {row["code"]: i for i, row in enumerate(self.agents)}
        self.loaded_at = time.time()
        logger.info(
            "registry loaded: %d agents from %s (generatedAt=%s)",
            self.total,
            self.path,
            self.generated_at,
        )

    def get(self, code: str) -> dict[str, Any] | None:
        idx = self._by_code.get(code)
        if idx is None:
            return None
        return self.agents[idx]


REGISTRY = Registry(REGISTRY_PATH)


# ── HTTP handlers ───────────────────────────────────────────────────────


async def handle_healthz(_request: web.Request) -> web.Response:
    return web.json_response({
        "ok": REGISTRY.total > 0,
        "service": "UnispscRegistryCell",
        "agentCount": REGISTRY.total,
        "generatedAt": REGISTRY.generated_at,
        "registryPath": str(REGISTRY.path),
        "loadedAt": REGISTRY.loaded_at,
    })


async def handle_list_agents(request: web.Request) -> web.Response:
    prefix = request.query.get("prefix") or ""
    try:
        cursor = int(request.query.get("cursor") or 0)
    except ValueError:
        return web.json_response(
            {"status": "rejected", "error": "InvalidCursor"}, status=400
        )
    try:
        limit = int(request.query.get("limit") or 100)
    except ValueError:
        limit = 100
    limit = max(1, min(1000, limit))

    if prefix:
        filtered = [a for a in REGISTRY.agents if a["code"].startswith(prefix)]
    else:
        filtered = REGISTRY.agents
    page = filtered[cursor : cursor + limit]
    next_cursor = (
        str(cursor + limit) if cursor + limit < len(filtered) else None
    )
    out: dict[str, Any] = {
        "agents": [
            {
                "code": a["code"],
                "handle": a.get("handle", f"c{a['code']}"),
                "did": f"{DID_ENTITY}:actor:{a.get('handle', 'c' + a['code'])}",
                "title": a.get("title", ""),
                "segment": a.get("segment", a["code"][:2]),
            }
            for a in page
        ],
        "totalCount": len(filtered),
    }
    if next_cursor is not None:
        out["cursor"] = next_cursor
    return web.json_response(out)


async def handle_get_agent(request: web.Request) -> web.Response:
    code = request.match_info["code"]
    row = REGISTRY.get(code)
    if row is None:
        return web.json_response(
            {"status": "notFound", "error": "AgentNotFound", "code": code},
            status=404,
        )
    return web.json_response({
        "code": row["code"],
        "handle": row.get("handle", f"c{code}"),
        "did": f"{DID_ENTITY}:actor:{row.get('handle', 'c' + code)}",
        "title": row.get("title", ""),
        "segment": row.get("segment", code[:2]),
    })


# ── cell-runner contract ────────────────────────────────────────────────


def healthz() -> dict[str, Any]:
    return {
        "ok": REGISTRY.total > 0,
        "service": "UnispscRegistryCell",
        "agentCount": REGISTRY.total,
    }


async def serve(stop_event: asyncio.Event, healthz_port: int, api_port: int) -> None:
    """Cell-runner entrypoint. Starts the HTTP listener and blocks."""
    if REGISTRY.total == 0:
        REGISTRY.load()

    api = web.Application()
    api.router.add_get("/healthz", handle_healthz)
    api.router.add_get("/api/listAgents", handle_list_agents)
    api.router.add_get("/api/agent/{code}", handle_get_agent)

    runner = web.AppRunner(api)
    await runner.setup()

    sites = [
        web.TCPSite(runner, "0.0.0.0", api_port),
    ]
    if healthz_port != api_port:
        sites.append(web.TCPSite(runner, "0.0.0.0", healthz_port))
    for site in sites:
        await site.start()
    logger.info(
        "UnispscRegistryCell serving on 0.0.0.0:%d (healthz=%d) — %d agents",
        api_port,
        healthz_port,
        REGISTRY.total,
    )
    try:
        await stop_event.wait()
    finally:
        await runner.cleanup()
        logger.info("UnispscRegistryCell shut down")


__all__ = ["Registry", "REGISTRY", "healthz", "serve"]
