"""
kotoba-kotodama-cell-runner — Murakumo fleet cell daemon entrypoint.

Per ADR-2605192415 §7.1 (Daemon Architecture — Murakumo Fleet Tier 1 launchd 常駐).

Reads `50-infra/murakumo/fleet.toml` to determine which cells to host
on the current node, then spawns each cell as a managed subprocess.

Each cell:
  - Loads its LangGraph StateGraph (from `20-actors/kotoba-kotodama/cells/<name>/cell.py`)
  - Connects MstCheckpointSaver sidecar (ADR-2605191559)
  - Subscribes to MST listener for its triggering Lexicon
  - Exposes healthz HTTP endpoint
  - Participates in swarm leader election (ADR-2605191603)

Usage:
    uv run kotoba-kotodama-cell-runner --node naphtali
    uv run kotoba-kotodama-cell-runner --node naphtali --cell-only CharterAttestationRequestCell  # debug

Configuration:
    fleet.toml: 50-infra/murakumo/fleet.toml
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


# In-container Pods set FLEET_TOML + ETZ_REPO via the fleet-to-kustomize
# generator (per ADR-2605232100). On a developer laptop the env vars are
# absent and we fall back to repo-relative resolution from __file__.
_ENV_REPO = os.environ.get("ETZ_REPO")
REPO_ROOT = Path(_ENV_REPO) if _ENV_REPO else Path(__file__).resolve().parents[5]
FLEET_TOML = Path(os.environ.get("FLEET_TOML") or (REPO_ROOT / "50-infra" / "murakumo" / "fleet.toml"))
CELLS_TOML = REPO_ROOT / "50-infra" / "cluster" / "murakumo" / "cell-runner" / "cells.toml"
CELLS_DIR = REPO_ROOT / "20-actors" / "kotoba-kotodama" / "cells"

HEALTHZ_PORT_DEFAULT = 13000

logger = logging.getLogger("kotoba-kotodama-cell-runner")
_log = logger  # alias used by M3 helpers for consistent naming

# Registry of spawned cell subprocesses (cell_name → Popen).
_cell_processes: dict[str, subprocess.Popen] = {}

# Track running asyncio cell tasks for graceful shutdown.
_cell_tasks: list[asyncio.Task] = []

# Module-level metadata list populated by spawn_cells_for_node.
_active_cells_metadata: list[dict] = []

# Process start time for uptime reporting.
_start_time: float = time.time()


def load_fleet_config(path: Path = FLEET_TOML) -> dict:
    """Load fleet.toml configuration."""
    if not path.exists():
        raise FileNotFoundError(f"fleet config not found: {path}")
    with path.open("rb") as f:
        return tomllib.load(f)


def get_node_cells(config: dict, node_name: str) -> list[str]:
    """Get list of cells assigned to the given node."""
    for node in config.get("nodes", []):
        if node["name"] == node_name:
            return node.get("cells", [])
    raise ValueError(f"node not found in fleet config: {node_name}")


def get_cell_config(config: dict, cell_name: str) -> dict:
    """Get per-cell configuration block."""
    return config.get("cells", {}).get(cell_name, {})


def load_cell_registry(path: Path | None = None) -> dict:
    """Load cells.toml from default search paths, then merge in yorishiro fragments.

    Search order for the base registry:
      1. Explicit ``path`` argument (if provided)
      2. /etc/etzhayyim/cells.toml       (system-wide install)
      3. ~/.etzhayyim/cells.toml          (per-user install)
      4. CELLS_TOML (50-infra/cluster/murakumo/cell-runner/cells.toml in repo checkout)

    After loading the base, scans
    ``20-actors/kotoba-kotodama/cells/yorishiro_*/cells.toml.fragment`` and appends
    each fragment's ``[[cell]]`` entry. This means yorishiri register
    themselves with zero edits to the central cells.toml — drop the
    generator output into the tree and the cell-runner picks it up on
    next start (ADR-2605211900 + ADR-2605202200).

    Returns the merged dict, or an empty dict if neither base nor any
    fragment is found.
    """
    candidates: list[Path] = []
    if path is not None:
        candidates.append(path)
    candidates += [
        Path("/etc/etzhayyim/cells.toml"),
        Path.home() / ".etzhayyim" / "cells.toml",
        CELLS_TOML,
    ]
    registry: dict = {}
    for candidate in candidates:
        if candidate.exists():
            logger.debug("cell registry: loading %s", candidate)
            with open(candidate, "rb") as f:
                registry = tomllib.load(f)
            break
    else:
        logger.debug("cell registry: no cells.toml found in search path; starting empty")

    # Yorishiro auto-discovery (ADR-2605211900). Each emitted yorishiro
    # ships a cells.toml.fragment alongside its cell.py; merge them here
    # so the generator output is self-contained.
    base_cells = list(registry.get("cell", []))
    fragment_paths = sorted(CELLS_DIR.glob("yorishiro_*/cells.toml.fragment")) + sorted(CELLS_DIR.glob("ossekai_*/cells.toml.fragment"))
    yorishiro_count = 0
    for frag in fragment_paths:
        try:
            with open(frag, "rb") as f:
                frag_data = tomllib.load(f)
        except Exception:
            logger.exception("cell registry: failed to load fragment %s", frag)
            continue
        for cell in frag_data.get("cell", []):
            base_cells.append(cell)
            yorishiro_count += 1
    if yorishiro_count:
        logger.info(
            "cell registry: merged %d yorishiro cell(s) from %d fragment(s) under %s",
            yorishiro_count,
            len(fragment_paths),
            CELLS_DIR,
        )
        registry = {**registry, "cell": base_cells}

    # Ensure 20-actors/kotoba-kotodama/cells/ is on sys.path so importlib can
    # resolve `yorishiro_<name>.cell` (each cell ships its own __init__.py
    # under that directory).
    cells_dir_str = str(CELLS_DIR)
    if cells_dir_str not in sys.path:
        sys.path.insert(0, cells_dir_str)
        logger.debug("cell registry: prepended %s to sys.path", cells_dir_str)

    return registry


def cells_for_node(registry: dict, node_name: str) -> list[dict]:
    """Filter [[cell]] entries from cells.toml for the given node.

    Returns cells whose ``node`` field equals ``node_name`` or ``"*"``
    (wildcard — runs on any node).

    Args:
        registry:  Parsed cells.toml dict (from load_cell_registry()).
        node_name: Murakumo tribe name (e.g. "levi", "simeon").

    Returns:
        List of cell dicts matching this node. Empty list if no registry or no match.
    """
    cells = registry.get("cell", [])
    return [c for c in cells if c.get("node") in (node_name, "*")]


# ── M3: Cell dispatch helpers ─────────────────────────────────────────────────


def _import_cell_entry(module_path: str, entry_name: str) -> Callable[..., Awaitable[Any]]:
    """Dynamically import a cell entry function."""
    module = importlib.import_module(module_path)
    fn = getattr(module, entry_name)
    if not callable(fn):
        raise RuntimeError(f"cell entry {module_path}.{entry_name} is not callable")
    return fn  # type: ignore[return-value]


def _cron_to_interval_s(expr: str) -> int:
    """Parse cron expression → interval seconds.

    Supports:
        "*/N * * * *" → N*60 seconds (every N minutes)
        "0 * * * *"   → 3600 seconds (hourly at :00)
        "0 */N * * *" → N*3600 seconds (every N hours)
        otherwise     → 3600 seconds (default hourly)
    """
    parts = expr.split()
    if len(parts) != 5:
        return 3600
    minute, hour, _, _, _ = parts
    if minute.startswith("*/"):
        try:
            return int(minute[2:]) * 60
        except ValueError:
            return 3600
    if minute == "0" and hour == "*":
        return 3600
    if minute == "0" and hour.startswith("*/"):
        try:
            return int(hour[2:]) * 3600
        except ValueError:
            return 3600
    return 3600


async def _spawn_cron_cell(cell: dict[str, Any], stop_event: asyncio.Event) -> None:
    """Spawn a cron-triggered cell.  Sleeps until next tick then fires entry.

    For simplicity, parse only "*/N * * * *", "0 * * * *", or "0 */N * * *"
    patterns.  Full croniter is the M4 enhancement.
    """
    name = cell.get("name", "<unnamed>")
    module_path = cell.get("module")
    entry_name = cell.get("entry")
    trigger = cell.get("trigger") or {}
    expr = trigger.get("expr", "0 * * * *")

    try:
        cell_fn = _import_cell_entry(module_path, entry_name)
    except Exception as e:
        _log.error("cron-cell %s: import failed: %s", name, e)
        return

    interval_s = _cron_to_interval_s(expr)
    _log.info("cron-cell %s: every %ds (expr=%s)", name, interval_s, expr)

    while not stop_event.is_set():
        try:
            # Wait until next tick or stop_event fires.
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_s)
                return  # Stop event triggered before next tick.
            except asyncio.TimeoutError:
                pass  # Fall through to invoke.

            _log.debug("cron-cell %s firing", name)
            await cell_fn()
        except Exception as e:
            _log.error("cron-cell %s: invocation failed: %s", name, e, exc_info=True)


def _extract_adherent_did(event: dict[str, Any]) -> str | None:
    """Extract adherentDid (or actorDid) from a firehose event's first record op."""
    ops = event.get("ops") or []
    for op in ops:
        path = op.get("path", "")
        if "/" in path:
            return event.get("repo")
    return None


async def _spawn_listener_cell(cell: dict[str, Any], stop_event: asyncio.Event) -> None:
    """Spawn an mst-listener-triggered cell.

    Subscribes via cursor helper, filters by listens_to collection, invokes
    the entry function on match.
    """
    name = cell.get("name", "<unnamed>")
    module_path = cell.get("module")
    entry_name = cell.get("entry")
    trigger = cell.get("trigger") or {}
    collections = trigger.get("listens_to", [])
    if not collections:
        _log.warning("listener-cell %s: no listens_to collections specified", name)
        return

    try:
        cell_fn = _import_cell_entry(module_path, entry_name)
    except Exception as e:
        _log.error("listener-cell %s: import failed: %s", name, e)
        return

    try:
        from etzhayyim_sdk import cursor as _cursor_mod
    except ImportError as e:
        _log.error("listener-cell %s: etzhayyim_sdk.cursor not available: %s", name, e)
        return

    cursor_id = f"cell-runner.{name}"
    _log.info(
        "listener-cell %s: subscribing to %s (cursor_id=%s)", name, collections, cursor_id
    )

    try:
        async for event in _cursor_mod.subscribe_with_checkpoint(
            cursor_id=cursor_id,
            collections=collections,
        ):
            if stop_event.is_set():
                return
            try:
                adherent_did = _extract_adherent_did(event)
                if adherent_did:
                    await cell_fn(adherent_did)
                else:
                    await cell_fn()
            except Exception as e:
                _log.error(
                    "listener-cell %s: invocation failed: %s", name, e, exc_info=True
                )
    except Exception as e:
        _log.error(
            "listener-cell %s: subscriber loop crashed: %s", name, e, exc_info=True
        )


async def _cell_runner_healthz(request: Any) -> Any:
    """Cell-runner liveness probe. Returns 200 with cell catalog if alive."""
    from aiohttp import web as _web

    cells_loaded = len(_active_cells_metadata)
    return _web.json_response({
        "ok": True,
        "service": "kotoba-kotodama-cell-runner",
        "node": os.environ.get("ETZHAYYIM_NODE_NAME", "unknown"),
        "cells_loaded": cells_loaded,
        "cells": [
            {"name": c.get("name"), "trigger": (c.get("trigger") or {}).get("kind")}
            for c in _active_cells_metadata
        ],
        "uptime_s": int(time.time() - _start_time),
    })


async def _cell_runner_kotoba-datomic_attest(request: Any) -> Any:
    """kotoba-datomic witness endpoint. Receives a WitnessRequest from the
    orchestrator (`@etzhayyim/sdk/kotoba-datomic`), produces a signed
    attestation against this node's hosted cells, and writes the
    resulting `com.etzhayyim.kotoba-datomic.attestation` record back to PDS.

    Wire contract (matches TS `WitnessTransport.requestAttestation`):

        POST /kotoba-datomic/attest
        Content-Type: application/json
        {
          "v": 1,
          "cellId": "<the cell selected by the orchestrator>",
          "recordUri": "at://...",
          "recordCid": "bafy...",
          "record": { ... domain record being attested ... },
          "rule": { ... com.etzhayyim.kotoba-datomic.membraneRule shape ... }
        }

    Response:
      202 Accepted — attestation queued (will appear on PDS shortly).
      404           — the requested cellId is not hosted on this node.
      400           — malformed body.
      500           — internal error during attestation.

    Per ADR-2605231400 §"Implementation plan" #2 + kotoba-datomic SPEC §5.
    """
    from aiohttp import web as _web
    from .kotoba-datomic import (
        WitnessRequest,
        make_cell_signer,
        produce_attestation,
    )

    try:
        body = await request.json()
    except Exception as caught:  # noqa: BLE001
        return _web.json_response(
            {"error": "invalid-json", "detail": str(caught)},
            status=400,
        )

    try:
        req = WitnessRequest.from_wire(body)
    except (KeyError, TypeError, ValueError) as caught:
        return _web.json_response(
            {"error": "invalid-request-shape", "detail": str(caught)},
            status=400,
        )

    cell_id = body.get("cellId")
    if not isinstance(cell_id, str) or not cell_id:
        return _web.json_response({"error": "missing-cellId"}, status=400)

    # Check the cell is hosted on this node. The cell_runner's active
    # metadata list is populated at spawn time.
    hosted_cell_ids = {c.get("name") for c in _active_cells_metadata}
    if cell_id not in hosted_cell_ids:
        return _web.json_response(
            {
                "error": "cell-not-hosted",
                "cellId": cell_id,
                "node": os.environ.get("ETZHAYYIM_NODE_NAME", "unknown"),
                "hosted": sorted(c for c in hosted_cell_ids if isinstance(c, str)),
            },
            status=404,
        )

    node_name = os.environ.get("ETZHAYYIM_NODE_NAME", "unknown")

    # Resolver chain: macOS Keychain (production) → env var (container
    # deploys, e.g. K8s Secret-injected) → deterministic test signer
    # (dev / unit-test only; logged loudly so it's not used in prod).
    # Per fleet.toml `cell_key_rotation_period_days = 90`, operator runs
    # `security add-generic-password -s com.etzhayyim.kotoba-datomic -a {cellId} -w '{hexSeed}'`
    # quarterly to rotate.
    signer, signer_source = make_cell_signer(cell_id)
    if signer_source == "deterministic":
        _log.warning(
            "kotoba-datomic.attest cellId=%s using DETERMINISTIC TEST SIGNER — "
            "production deploys must publish a real Ed25519 key to macOS "
            "Keychain (service=com.etzhayyim.kotoba-datomic, account=%s) OR set "
            "CELL_PRIVATE_KEY_%s env var (hex 32-byte seed)",
            cell_id, cell_id, cell_id,
        )

    try:
        attestation = await produce_attestation(
            record_uri=req.record_uri,
            record_cid=req.record_cid,
            record=req.record,
            rule=req.rule,
            cell_id=cell_id,
            cell_node=node_name,
            signer=signer,
        )
    except Exception as caught:  # noqa: BLE001
        _log.error(
            "kotoba-datomic.attest cellId=%s failed during produce_attestation: %s",
            cell_id, caught, exc_info=True,
        )
        return _web.json_response(
            {"error": "produce-attestation-failed", "detail": str(caught)},
            status=500,
        )

    # Write the attestation back to PDS via kotodama.substrate.
    # Skipped in unit tests (SUBSTRATE_WRITE_DISABLED=1) — they assert
    # against the produced attestation shape directly.
    if os.environ.get("SUBSTRATE_WRITE_DISABLED", "0") != "1":
        try:
            from .substrate import Etzhayyim, WriteOpts

            substrate_did = os.environ.get("KOTOBA_DATOMIC_ATTESTATION_DID", node_name)
            async with Etzhayyim(did=substrate_did) as e:
                await e.write(
                    WriteOpts(
                        collection="com.etzhayyim.kotoba-datomic.attestation",
                        record=attestation.to_wire(),
                    )
                )
        except Exception as caught:  # noqa: BLE001
            # PDS write failures are logged but don't fail the orchestrator
            # — the attestation is lost for this quorum but won't 500 here.
            # Orchestrator will time out the slot and either reduce quorum
            # or escalate per rule.escalationPolicy.
            _log.warning(
                "kotoba-datomic.attest cellId=%s PDS write failed: %s",
                cell_id, caught,
            )

    return _web.json_response(
        {
            "ok": True,
            "verdict": attestation.verdict,
            "quorumGroup": attestation.quorum_group,
            "cellId": cell_id,
            "cellNode": node_name,
        },
        status=202,
    )


async def _start_healthz_server(port: int) -> None:
    """Run /healthz + /kotoba-datomic/attest endpoints as concurrent asyncio task.

    Bind defaults to 127.0.0.1 (launchd / local-dev). In-Pod deploys per
    ADR-2605232100 set ETZ_HEALTHZ_BIND=0.0.0.0 so kubelet probes against
    PodIP reach the listener.
    """
    from aiohttp import web as _web

    bind = os.environ.get("ETZ_HEALTHZ_BIND", "127.0.0.1")
    app = _web.Application()
    app.router.add_get("/healthz", _cell_runner_healthz)
    app.router.add_post("/kotoba-datomic/attest", _cell_runner_kotoba-datomic_attest)
    runner = _web.AppRunner(app)
    await runner.setup()
    site = _web.TCPSite(runner, bind, port)
    await site.start()
    _log.info(
        "cell-runner http://%s:%d {/healthz, /kotoba-datomic/attest}", bind, port
    )


async def _spawn_xrpc_cell(cell: dict[str, Any], stop_event: asyncio.Event) -> None:
    """Register an xrpc-triggered cell.

    XRPC cells (typical of yorishiri — ADR-2605211900) are invoked on
    demand from the XRPC gateway, not driven by a continuous loop. The
    cell-runner's job here is to:

      1. Import the cell module so it's resolvable when the gateway
         dispatches to it (build_graph is the contract entry point).
      2. Surface the cell in /healthz so operators can confirm it's loaded.
      3. Sit idle until stop_event fires.

    The actual XRPC dispatch — incoming request → state_from_event →
    compiled graph → response — happens in the gateway layer, not here.
    """
    name = cell.get("name", "<unnamed>")
    module_path = cell.get("module")
    nsid = (cell.get("trigger") or {}).get("nsid", "<no-nsid>")

    if not module_path:
        _log.error("xrpc-cell %s: no module path declared, refusing to load", name)
        return

    try:
        importlib.import_module(module_path)
    except Exception as e:  # noqa: BLE001 — surface module loading failures
        _log.error("xrpc-cell %s: import failed (%s): %s", name, module_path, e)
        return

    _log.info("xrpc-cell %s: registered (module=%s nsid=%s)", name, module_path, nsid)
    # Idle until shutdown — the cell is now callable from the XRPC gateway.
    await stop_event.wait()


async def _spawn_lan_api_cell(cell: dict[str, Any], stop_event: asyncio.Event) -> None:
    """Spawn a LAN-API cell: the module owns its own aiohttp listener.

    Per ADR-2605171300 + ADR-2605192415 (UnispscRegistryCell + UnispscAgent-
    ExecutorCell): the cell exposes an HTTP service inside the fleet LAN that
    the XRPC façade (yoro-xrpc-adapter on CF) reaches via tunnel. Unlike
    xrpc-cells, these are NOT dispatched by an in-process gateway — they hold
    their own socket.

    Contract: the imported module exports
        async def serve(stop_event, healthz_port, api_port) -> None
    """
    name = cell.get("name", "<unnamed>")
    module_path = cell.get("module")
    trigger = cell.get("trigger") or {}
    healthz_port = int(trigger.get("healthz_port") or cell.get("healthz_port") or 0)
    api_port = int(trigger.get("api_port") or cell.get("api_port") or healthz_port)

    if not module_path:
        _log.error("lan-api-cell %s: no module path declared", name)
        return
    if not healthz_port or not api_port:
        _log.error(
            "lan-api-cell %s: missing healthz_port/api_port (healthz=%s api=%s)",
            name, healthz_port, api_port,
        )
        return

    try:
        mod = importlib.import_module(module_path)
    except Exception as e:  # noqa: BLE001
        _log.error("lan-api-cell %s: import failed (%s): %s", name, module_path, e)
        return

    serve_fn = getattr(mod, "serve", None)
    if not callable(serve_fn):
        _log.error("lan-api-cell %s: module %s has no async serve()", name, module_path)
        return

    _log.info(
        "lan-api-cell %s: starting (module=%s healthz=%d api=%d)",
        name, module_path, healthz_port, api_port,
    )
    try:
        await serve_fn(stop_event, healthz_port, api_port)
    except Exception as e:  # noqa: BLE001 — keep runner alive across one cell's crash
        _log.exception("lan-api-cell %s: serve() crashed: %s", name, e)


async def spawn_cells_for_node(
    cells: list[dict[str, Any]], stop_event: asyncio.Event
) -> None:
    """Spawn all cells for this node as concurrent asyncio tasks."""
    global _active_cells_metadata
    _active_cells_metadata = list(cells)

    for cell in cells:
        trigger = cell.get("trigger") or {}
        kind = trigger.get("kind", "")
        if kind == "cron":
            task = asyncio.create_task(_spawn_cron_cell(cell, stop_event))
        elif kind == "mst-listener":
            task = asyncio.create_task(_spawn_listener_cell(cell, stop_event))
        elif kind == "xrpc":
            task = asyncio.create_task(_spawn_xrpc_cell(cell, stop_event))
        elif kind == "lan-api":
            task = asyncio.create_task(_spawn_lan_api_cell(cell, stop_event))
        else:
            _log.warning(
                "cell %s: unknown trigger kind %r, skipping", cell.get("name"), kind
            )
            continue
        _cell_tasks.append(task)

    if _cell_tasks:
        await asyncio.gather(*_cell_tasks, return_exceptions=True)


async def _async_main(node_name: str, cells: list[dict[str, Any]]) -> None:
    """Async main loop. Spawns cells and waits for shutdown."""
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    healthz_port = int(
        os.environ.get("ETZHAYYIM_CELL_RUNNER_HEALTHZ_PORT", str(HEALTHZ_PORT_DEFAULT))
    )
    asyncio.create_task(_start_healthz_server(healthz_port))

    _log.info(
        "cell-runner: spawning %d cells for node %s", len(cells), node_name
    )
    await spawn_cells_for_node(cells, stop_event)
    _log.info("cell-runner: all cells exited cleanly")


# ── End M3 helpers ────────────────────────────────────────────────────────────


def _cell_dir(cell_name: str) -> Path:
    """Map CamelCase cell name to its directory.

    Delegates to kotodama.cell_host._cell_dir for the SSoT mapping so
    runner + host stay in sync.
    """
    from kotodama.cell_host import _cell_dir as host_cell_dir

    return host_cell_dir(cell_name)


def start_cell(node_name: str, cell_name: str, cell_config: dict, log_dir: Path) -> subprocess.Popen | None:
    """Spawn a cell as a managed subprocess via `python -m kotodama.cell_host`.

    Per ADR-2605202200 §4. Returns the Popen handle (or None on skip).

    Each subprocess:
      - Imports cell.py from 20-actors/kotoba-kotodama/cells/<name>/cell.py
      - Builds CellDeps + invokes build_graph(deps)
      - Starts the trigger loop declared in fleet.toml [cells.<name>]
      - Serves /healthz on cell_config['healthz_port']
      - Listens for SIGTERM → graceful drain → exit 0
    """
    healthz_port = cell_config.get("healthz_port")
    trigger = cell_config.get("trigger", "unknown")
    listens_to = cell_config.get("listens_to", [])
    cron = cell_config.get("cron", "")
    api_port = cell_config.get("api_port", 0)

    logger.info(
        "[%s] starting cell %s (trigger=%s, healthz_port=%s)",
        node_name,
        cell_name,
        trigger,
        healthz_port,
    )

    cell_dir = _cell_dir(cell_name)
    cell_py = cell_dir / "cell.py"
    if not cell_py.exists():
        logger.warning("[%s] cell.py not found for %s (looked at %s); skipping", node_name, cell_name, cell_py)
        return None

    if healthz_port is None:
        logger.warning("[%s] %s: healthz_port not configured in fleet.toml; skipping", node_name, cell_name)
        return None

    # Build the cell_host subprocess command
    cmd = [
        sys.executable,  # the same Python interpreter that's running cell-runner
        "-m",
        "kotodama.cell_host",
        "--cell", cell_name,
        "--node", node_name,
        "--healthz-port", str(healthz_port),
        "--trigger", trigger,
        "--log-level", logger.getEffectiveLevel().__class__.__name__ if False else os.environ.get("LOG_LEVEL", "INFO"),
    ]
    for nsid in listens_to:
        cmd.extend(["--listens-to", nsid])
    if cron:
        cmd.extend(["--cron", cron])
    if api_port:
        cmd.extend(["--api-port", str(api_port)])

    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / f"cell-{cell_name}.stdout.log"
    stderr_path = log_dir / f"cell-{cell_name}.stderr.log"

    # Inherit env, allow per-cell env overrides via fleet.toml [cells.<name>.env] (future)
    env = os.environ.copy()
    env.setdefault("ETZHAYYIM_NODE", node_name)
    env.setdefault("ETZHAYYIM_CELL", cell_name)

    try:
        # Open log files; subprocess writes directly (avoids parent stdio buffer)
        stdout_f = stdout_path.open("ab", buffering=0)
        stderr_f = stderr_path.open("ab", buffering=0)
        proc = subprocess.Popen(
            cmd,
            stdout=stdout_f,
            stderr=stderr_f,
            stdin=subprocess.DEVNULL,
            env=env,
            cwd=str(REPO_ROOT),
        )
    except Exception as e:
        logger.exception("[%s] failed to spawn %s: %s", node_name, cell_name, e)
        return None

    _cell_processes[cell_name] = proc
    logger.info("[%s] spawned %s pid=%d (healthz=127.0.0.1:%s)", node_name, cell_name, proc.pid, healthz_port)
    return proc


def stop_all_cells(timeout: float = 30.0) -> None:
    """Send SIGTERM to all spawned cell subprocesses, then SIGKILL after timeout."""
    if not _cell_processes:
        return
    logger.info("propagating SIGTERM to %d cell subprocesses", len(_cell_processes))
    for cell_name, proc in _cell_processes.items():
        if proc.poll() is None:
            try:
                proc.terminate()
                logger.info("  - %s pid=%d SIGTERM sent", cell_name, proc.pid)
            except Exception:
                logger.exception("  - %s SIGTERM failed", cell_name)
    deadline = time.time() + timeout
    for cell_name, proc in list(_cell_processes.items()):
        remaining = max(0.0, deadline - time.time())
        try:
            proc.wait(timeout=remaining)
            logger.info("  - %s exited with code %s", cell_name, proc.returncode)
        except subprocess.TimeoutExpired:
            logger.warning("  - %s did not exit within timeout; SIGKILL", cell_name)
            try:
                proc.kill()
            except Exception:
                pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kotoba-kotodama-cell-runner")
    parser.add_argument("--node", required=True, help="Murakumo node name (e.g., naphtali)")
    parser.add_argument("--cell-only", default=None, help="Run only this single cell (debug)")
    parser.add_argument("--fleet-toml", default=str(FLEET_TOML), help="Path to fleet.toml")
    parser.add_argument("--health", action="store_true", help="Print health status and exit")
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument(
        "--log-dir",
        default=os.environ.get("ETZHAYYIM_LOG_DIR", str(Path.home() / ".etzhayyim" / "log")),
        help="Directory for per-cell stdout/stderr log files",
    )
    parser.add_argument(
        "--cells-toml",
        default=None,
        help="Path to cells.toml registry (default: auto-detected search path)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        config = load_fleet_config(Path(args.fleet_toml))
        cells = get_node_cells(config, args.node)
    except (FileNotFoundError, ValueError) as e:
        logger.error("config error: %s", e)
        return 1

    # Load cells.toml registry and log the catalog for this node.
    # ETZHAYYIM_NODE_NAME is set by the launchd plist (com.etzhayyim.kotoba-kotodama-cell-runner.plist).
    # Full cell spawning (cron scheduler + mst-listener loop) is deferred to M3.
    cells_toml_path = Path(args.cells_toml) if args.cells_toml else None
    registry = load_cell_registry(cells_toml_path)
    node_name_for_registry = os.environ.get("ETZHAYYIM_NODE_NAME", args.node)
    my_cells_registry = cells_for_node(registry, node_name_for_registry)
    logger.info(
        "cell-runner: loaded %d cells for node %s from cells.toml registry",
        len(my_cells_registry),
        node_name_for_registry,
    )
    for cell_entry in my_cells_registry:
        logger.debug(
            "  registry cell: name=%s module=%s entry=%s trigger=%s healthz_port=%s",
            cell_entry.get("name"),
            cell_entry.get("module"),
            cell_entry.get("entry"),
            cell_entry.get("trigger"),
            cell_entry.get("healthz_port"),
        )
    # M3: spawn asyncio cell loops for all cells in the registry for this node.
    # This runs _async_main which schedules cron + mst-listener tasks and blocks
    # until a stop_event fires.  Placed here so the health-check path below can
    # still exit early without entering the event loop.
    _registry_spawn_cells = my_cells_registry  # captured for use after arg checks

    if args.cell_only:
        if args.cell_only not in cells:
            logger.error("cell %s not assigned to node %s (assigned: %s)", args.cell_only, args.node, cells)
            return 1
        cells = [args.cell_only]

    if args.health:
        print(f"node: {args.node}")
        print(f"cells assigned: {len(cells)}")
        for c in cells:
            print(f"  - {c}")
        return 0

    log_dir = Path(args.log_dir)
    logger.info("starting %d cells on node %s (log_dir=%s)", len(cells), args.node, log_dir)
    for cell_name in cells:
        cell_config = get_cell_config(config, cell_name)
        start_cell(args.node, cell_name, cell_config, log_dir)

    # M3: run the asyncio event loop that drives cron + mst-listener cells from
    # cells.toml.  Signal handling (SIGTERM/SIGINT → stop_event) is done inside
    # _async_main via loop.add_signal_handler, which supersedes the old sync
    # handle_sigterm approach for the asyncio path.  stop_all_cells() is called
    # in the finally block so fleet.toml subprocesses are always reaped cleanly.
    if _registry_spawn_cells:
        try:
            asyncio.run(_async_main(node_name_for_registry, _registry_spawn_cells))
        finally:
            logger.info(
                "cell-runner exiting on %s — propagating SIGTERM to %d fleet cells",
                args.node,
                len(_cell_processes),
            )
            stop_all_cells(timeout=30.0)
            logger.info("cell-runner exited on %s", args.node)
    else:
        # No cells.toml cells for this node — fall back to the original sync
        # signal-wait loop so fleet.toml subprocesses are still supervised.
        shutdown_requested = False

        def handle_sigterm(signum, frame):
            nonlocal shutdown_requested
            logger.info("shutdown signal received (%d)", signum)
            shutdown_requested = True

        signal.signal(signal.SIGTERM, handle_sigterm)
        signal.signal(signal.SIGINT, handle_sigterm)

        logger.info("cell-runner active on %s; awaiting signals", args.node)
        while not shutdown_requested:
            time.sleep(1)
            # Reap dead children + log; full restart policy is launchd's job.
            for cell_name, proc in list(_cell_processes.items()):
                rc = proc.poll()
                if rc is not None and rc != 0:
                    logger.warning(
                        "[%s] cell %s exited unexpectedly with code %s",
                        args.node,
                        cell_name,
                        rc,
                    )
                    del _cell_processes[cell_name]

        logger.info(
            "cell-runner exiting on %s — propagating SIGTERM to %d cells",
            args.node,
            len(_cell_processes),
        )
        stop_all_cells(timeout=30.0)
        logger.info("cell-runner exited on %s", args.node)
    return 0


if __name__ == "__main__":
    sys.exit(main())
