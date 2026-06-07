"""XRPC façade for ``com.etzhayyim.apps.unispsc.*``.

Mounted by :mod:`kotodama.langgraph_server_app` so that every UNSPSC
commodity agent under ``kotodama.langgraph_graphs.unispsc_agents.c{code}``
is reachable through the unified ``etzhayyim.com/xrpc/`` gateway without
needing a per-actor subdomain.

Endpoints (matching ``00-contracts/lexicons/com/etzhayyim/apps/unispsc/*.json``):

* ``GET  /xrpc/com.etzhayyim.apps.unispsc.health``        → :func:`health`
* ``GET  /xrpc/com.etzhayyim.apps.unispsc.listAgents``    → :func:`list_agents`
* ``POST /xrpc/com.etzhayyim.apps.unispsc.invokeAgent``   → :func:`invoke_agent`
* ``POST /xrpc/com.etzhayyim.apps.unispsc.classify``      → :func:`classify`

The agent registry is **lazy**: ``c{code}.py`` is imported on first call and
the compiled ``graph`` is cached in an in-process LRU. Cold-start cost for
one agent is ~50 ms (StateGraph compile).
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

LOG = logging.getLogger(__name__)

_BOOT_MS = int(time.time() * 1000)

_AGENTS_PKG = "kotodama.langgraph_graphs.unispsc_agents"
_CODE_RE = re.compile(r"^\d{4,12}$")


# ---------------------------------------------------------------------------
# Registry discovery (filesystem-backed, deterministic ordering)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _agents_dir() -> Path:
    """Locate the unispsc_agents directory on disk for listing.

    Resolves via the package ``__file__`` so it works whether the wheel is
    installed editable or relocated inside the container image.
    """
    mod = importlib.import_module(_AGENTS_PKG)
    paths = list(getattr(mod, "__path__", []))
    if not paths:
        raise RuntimeError(f"package {_AGENTS_PKG} has no __path__")
    return Path(paths[0])


@lru_cache(maxsize=1)
def _all_codes() -> tuple[str, ...]:
    """All commodity codes discoverable as ``c{code}.py`` modules.

    Sorted ascending for stable pagination cursors.
    """
    out: list[str] = []
    for f in _agents_dir().iterdir():
        if not f.is_file() or f.suffix != ".py":
            continue
        name = f.stem
        if not name.startswith("c"):
            continue
        code = name[1:]
        if _CODE_RE.match(code):
            out.append(code)
    out.sort()
    return tuple(out)


@lru_cache(maxsize=4096)
def _load_graph(code: str) -> Any:
    """Lazy-load + cache a commodity agent's compiled StateGraph."""
    if not _CODE_RE.match(code):
        raise ValueError(f"invalid commodity code: {code!r}")
    mod_name = f"{_AGENTS_PKG}.c{code}"
    try:
        mod = importlib.import_module(mod_name)
    except ImportError as e:
        raise LookupError(f"AgentNotFound: {mod_name}") from e
    graph = getattr(mod, "graph", None)
    if graph is None:
        raise RuntimeError(f"AgentLoadFailed: {mod_name} has no `graph` symbol")
    return graph


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class InvokeAgentInput(BaseModel):
    code: str = Field(min_length=4, max_length=12)
    payload: dict[str, Any]
    modelHint: str | None = Field(default="auto")
    timeoutMs: int = Field(default=10_000, ge=100, le=25_000)


class ClassifyInput(BaseModel):
    description: str = Field(min_length=1, max_length=4000)
    topK: int = Field(default=5, ge=1, le=20)
    modelHint: str = Field(default="auto")
    confidenceThreshold: float = Field(default=0.7, ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


router = APIRouter(prefix="/xrpc", tags=["unispsc"])


@router.get("/com.etzhayyim.apps.unispsc.health")
async def health() -> dict[str, Any]:
    codes = _all_codes()
    warm = _load_graph.cache_info().currsize  # type: ignore[attr-defined]
    status = "healthy" if codes else "degraded"
    return {
        "status": status,
        "registryReady": bool(codes),
        "agentCount": len(codes),
        "warmAgents": warm,
        "modelsAvailable": ["haiku-4.5", "sonnet-4.6"],
        "uptimeMs": int(time.time() * 1000) - _BOOT_MS,
    }


@router.get("/com.etzhayyim.apps.unispsc.listAgents")
async def list_agents(
    prefix: str | None = None,
    limit: int = 100,
    cursor: str | None = None,
) -> dict[str, Any]:
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="limit out of range [1,1000]")
    codes = _all_codes()
    if prefix:
        codes = tuple(c for c in codes if c.startswith(prefix))
    start = 0
    if cursor:
        try:
            start = int(cursor)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="invalid cursor") from e
    page = codes[start : start + limit]
    next_cursor = str(start + limit) if start + limit < len(codes) else None
    warm_keys: set[str] = set()
    try:
        # functools.lru_cache doesn't expose keys; track warmth via a side-channel
        # would require wrapping. For now, infer from cache_info — a coarse signal.
        pass
    except Exception:
        pass
    agents = [
        {
            "code": c,
            "module": f"{_AGENTS_PKG}.c{c}",
            "loaded": c in warm_keys,
        }
        for c in page
    ]
    return {
        "agents": agents,
        "totalCount": len(codes),
        **({"cursor": next_cursor} if next_cursor else {}),
    }


@router.post("/com.etzhayyim.apps.unispsc.invokeAgent")
async def invoke_agent(body: InvokeAgentInput) -> dict[str, Any]:
    started = time.time()
    try:
        graph = _load_graph(body.code)
    except LookupError as e:
        raise HTTPException(status_code=404, detail={"error": "AgentNotFound", "message": str(e)})
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=500, detail={"error": "AgentLoadFailed", "message": str(e)})

    # Stage D (per ADR-2605232100) — opt-in perceive/record wrapper around
    # the per-actor LangGraph. ETZ_UNISPSC_CAPABILITY_WRAP=1 turns on the
    # belief-store loop; without it the bare graph.ainvoke contract is
    # preserved for callers that don't expect the augmented response.
    from kotodama.unispsc_capabilities.wrapper import (
        capability_wrapping_enabled,
        invoke_with_capability,
    )

    try:
        if capability_wrapping_enabled():
            result = await invoke_with_capability(
                body.code,
                graph,
                body.payload,
                timeout_s=body.timeoutMs / 1000.0,
            )
        else:
            result = await asyncio.wait_for(
                graph.ainvoke(body.payload),
                timeout=body.timeoutMs / 1000.0,
            )
    except asyncio.TimeoutError:
        return {
            "ok": False,
            "error": "Timeout",
            "elapsedMs": int((time.time() - started) * 1000),
        }
    except Exception as e:  # noqa: BLE001 — surface to XRPC error envelope
        LOG.exception("invokeAgent failed code=%s", body.code)
        return {
            "ok": False,
            "error": "InvocationFailed",
            "elapsedMs": int((time.time() - started) * 1000),
            "result": {"message": str(e)},
        }

    return {
        "ok": True,
        "result": result,
        "modelUsed": body.modelHint or "auto",
        "elapsedMs": int((time.time() - started) * 1000),
    }


@router.post("/com.etzhayyim.apps.unispsc.classify")
async def classify(body: ClassifyInput) -> dict[str, Any]:
    """Description → top-K commodity codes.

    Phase-1 implementation: deterministic substring + token match against
    each agent's module name + a stub title (the code itself). When the
    open_unispsc primitive that owns the embedding index lands in the
    langserver image, this body switches to the Haiku-first / Sonnet-escalation
    path described in the lexicon ``description`` field.
    """
    started = time.time()
    desc = body.description.lower()
    tokens = [t for t in re.split(r"\W+", desc) if len(t) >= 3]
    candidates: list[dict[str, Any]] = []
    for code in _all_codes():
        score = 0.0
        if any(tok in code for tok in tokens):
            score += 0.2
        if score > 0:
            candidates.append(
                {
                    "code": code,
                    "confidence": min(score, 1.0),
                    "title": f"UNSPSC {code}",
                }
            )
    candidates.sort(key=lambda c: c["confidence"], reverse=True)
    return {
        "candidates": candidates[: body.topK],
        "modelUsed": "stub-substring",
        "escalated": False,
        "elapsedMs": int((time.time() - started) * 1000),
    }
