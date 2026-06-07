"""langserver_murakumo — fleet langserver health-monitoring Pregel cell (L9).

Reference implementation showing how a Pregel cell consumes
``langserver_client`` to query fleet LSPs. Cell name:
``LangserverHealthMonitoringCell``.

Trigger: cron */5 * * * * (every 5 minutes).
Placement: any node with healthz reachability — defaults to ``levi`` (the
membership / council orchestration node already running multiple cron
cells).

Behavior:
  1. Load lsp-fleet.json
  2. For each language entry, open an LSP session, send ``initialize``, and
     record latency + reachability
  3. Emit a single aggregated record per cycle (in-memory only at L9;
     wiring to MST listener ``com.etzhayyim.apps.etzhayyim.langserver.health``
     is a follow-up that requires lexicon registration).

The corresponding cells.toml entry is added in this same wave; see
``50-infra/cluster/murakumo/cell-runner/cells.toml``.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import os
from dataclasses import asdict, dataclass, field
from typing import Any

from kotodama.primitives.langserver_client import LangserverClient, load_registry

_log = logging.getLogger(__name__)


# ── Substrate-fit invariant ──────────────────────────────────────────────

if "runpod" in os.environ.get("PATH", "").lower() or os.environ.get("RW_URL"):
    raise ImportError(
        "langserver_murakumo religious-corp-only — RUNPOD/RW environment detected."
    )


# ── Result record ────────────────────────────────────────────────────────


@dataclass(slots=True)
class LangserverHealthResult:
    lang: str
    host: str
    mesh_ip: str
    port: int
    ok: bool
    initialize_latency_ms: int | None = None
    error: str | None = None
    capabilities_advertised: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LangserverHealthCycle:
    cycle_at: str  # UTC ISO8601
    results: list[LangserverHealthResult] = field(default_factory=list)
    ok_count: int = 0
    fail_count: int = 0


# ── Cell entrypoint ──────────────────────────────────────────────────────


async def langserver_health_monitoring_cell(
    *,
    registry_path: str | None = None,
    timeout_seconds: float = 10.0,
) -> LangserverHealthCycle:
    """LangserverHealthMonitoringCell — poll every fleet LSP via initialize.

    Placement: levi (cron */5 * * * *).

    Args:
        registry_path: override path to lsp-fleet.json (default: env / repo walk)
        timeout_seconds: per-LSP initialize timeout

    Returns:
        LangserverHealthCycle with one LangserverHealthResult per registry entry.

    Future work (post-L9):
        - Write to MST listener com.etzhayyim.apps.etzhayyim.langserver.health
          (requires lexicon registration under 00-contracts/lexicons/)
        - Flap detection: track consecutive failures and emit alert.did
          notification per fleet.toml [monitoring]
        - Workspace-deep probe: open a known fixture file and request
          hover/definition (validates LSP indexing not just protocol handshake)
    """
    endpoints = load_registry(registry_path)
    cycle = LangserverHealthCycle(
        cycle_at=datetime.datetime.now(datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
    )

    async def probe_one(lang: str) -> LangserverHealthResult:
        e = endpoints[lang]
        t0 = asyncio.get_running_loop().time()
        try:
            async with LangserverClient.connect(lang, registry_path=registry_path) as lsp:
                init_result = await asyncio.wait_for(
                    lsp.initialize(root_uri=None),
                    timeout=timeout_seconds,
                )
                elapsed_ms = int((asyncio.get_running_loop().time() - t0) * 1000)
                caps = list((init_result or {}).get("capabilities", {}).keys())
                return LangserverHealthResult(
                    lang=lang,
                    host=e.host,
                    mesh_ip=e.mesh_ip,
                    port=e.port,
                    ok=True,
                    initialize_latency_ms=elapsed_ms,
                    capabilities_advertised=caps,
                )
        except (asyncio.TimeoutError, OSError, RuntimeError) as exc:
            return LangserverHealthResult(
                lang=lang,
                host=e.host,
                mesh_ip=e.mesh_ip,
                port=e.port,
                ok=False,
                error=f"{type(exc).__name__}: {exc!r}",
            )

    # Probe all languages concurrently
    results = await asyncio.gather(*(probe_one(lang) for lang in endpoints))
    cycle.results.extend(results)
    cycle.ok_count = sum(1 for r in results if r.ok)
    cycle.fail_count = len(results) - cycle.ok_count

    _log.info(
        "LangserverHealthMonitoringCell: cycle=%s ok=%d fail=%d",
        cycle.cycle_at, cycle.ok_count, cycle.fail_count,
    )
    return cycle


def cycle_to_dict(cycle: LangserverHealthCycle) -> dict[str, Any]:
    """Convenience: serialize cycle to a JSON-ready dict (for downstream MST write)."""
    return {
        "cycle_at": cycle.cycle_at,
        "ok_count": cycle.ok_count,
        "fail_count": cycle.fail_count,
        "results": [asdict(r) for r in cycle.results],
    }
