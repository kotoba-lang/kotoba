"""
cell_host — per-cell subprocess entrypoint.

Per ADR-2605202200 (Cell runtime contract) §4.

Run as a subprocess by `kotoba-kotodama-cell-runner` on a Murakumo Mac mini.
One cell_host = one cell on one node. The host imports the target cell.py,
builds CellDeps, instantiates the LangGraph StateGraph via build_graph,
and drives it from the trigger declared in fleet.toml (mst-listener / cron /
synchronous API).

Usage (spawned by cell_runner_main):
    python -m kotodama.cell_host \
        --cell <CellName> \
        --node <NodeName> \
        --healthz-port <port> \
        --listens-to <NSID1> --listens-to <NSID2> \
        --trigger <mst-listener|cron|synchronous-api>

Lifecycle:
    1. Parse args
    2. Import cell module (20-actors/kotoba-kotodama/cells/<name>/cell.py)
    3. Build CellDeps (checkpointer / sdk / web3 ports / pds / llm)
    4. Call cell.on_startup(deps) if defined
    5. graph = cell.build_graph(deps)
    6. Start healthz HTTP server on healthz-port
    7. Start trigger loop:
         - mst-listener  : MstListener subscribes NSIDs, on_event → invoke
         - cron          : croniter schedule, on_tick → invoke
         - synchronous-api: serve POST /<cell>/invoke
    8. Block until SIGTERM
    9. On SIGTERM: cell.on_shutdown(deps) if defined → graceful drain → exit 0
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from kotodama.cell_runtime import (
    CellDeps,
    HealthzStatus,
    default_state_from_event,
    default_thread_id_from_event,
)

logger = logging.getLogger("kotoba-kotodama-cell-host")

# Same env override as cell_runner_main.py — ETZ_REPO redirects path
# resolution from `__file__.parents[5]` (installed-package layout) to a
# mounted repo root (orbstack hostPath, future ConfigMap). Per ADR-2605232100.
_ENV_REPO = os.environ.get("ETZ_REPO")
REPO_ROOT = Path(_ENV_REPO) if _ENV_REPO else Path(__file__).resolve().parents[5]
KOTODAMA_CELLS_DIR = REPO_ROOT / "20-actors" / "kotoba-kotodama" / "cells"
KUNI_UMI_CELLS_DIR = REPO_ROOT / "20-actors" / "kuni-umi" / "cells"


# Cell name → (cells_root, snake_case_subdir) overrides.
_CELL_DIR_OVERRIDES: dict[str, tuple[Path, str]] = {
    "PhenotypeAgent": (KOTODAMA_CELLS_DIR, "phenotype_agent"),
}

# kuni-umi cells live under 20-actors/kuni-umi/cells/ (ADR-2605201400 §1).
_KUNI_UMI_CELLS: set[str] = {
    "SiteSurveyCell",
    "DeploymentPlanningCell",
    "ConstructionOrchestrationCell",
    "CommissioningCell",
    "AuditWitnessCell",
    "DecommissionCell",
}

# Tier B religious-corp + kuni-umi fleet-rebalance cells planned at higher S levels.
_FLEET_REBALANCE_CELLS: set[str] = {"FleetRebalanceCell"}  # ADR-2605201800 S4


def _camel_to_snake(name: str) -> str:
    if name.endswith("Cell"):
        name = name[: -len("Cell")]
    out: list[str] = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0:
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


def _cell_dir(cell_name: str) -> Path:
    """Map CamelCase cell name to its directory.

    kuni-umi cells live under 20-actors/kuni-umi/cells/ (ADR-2605201400 §1).
    Religious-corp cells live under 20-actors/kotoba-kotodama/cells/ (ADR-2605192415).
    """
    if cell_name in _CELL_DIR_OVERRIDES:
        cells_root, snake = _CELL_DIR_OVERRIDES[cell_name]
        return cells_root / snake

    snake = _camel_to_snake(cell_name)

    if cell_name in _KUNI_UMI_CELLS:
        return KUNI_UMI_CELLS_DIR / snake
    if cell_name in _FLEET_REBALANCE_CELLS:
        return KUNI_UMI_CELLS_DIR / snake  # also kuni-umi
    return KOTODAMA_CELLS_DIR / snake


def import_cell_module(cell_name: str) -> Any:
    """Import the cell.py module for the given cell name."""
    cell_dir = _cell_dir(cell_name)
    cell_py = cell_dir / "cell.py"
    if not cell_py.exists():
        raise FileNotFoundError(f"cell.py not found for {cell_name} at {cell_py}")

    module_name = f"kotodama_cell_{cell_dir.name}"
    spec = importlib.util.spec_from_file_location(module_name, cell_py)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load spec for {cell_py}")
    module = importlib.util.module_from_spec(spec)
    # Register in sys.modules BEFORE exec so typing.get_type_hints() can resolve
    # forward refs like Literal[...] via the module's __dict__ (LangGraph's
    # StateGraph constructor calls get_type_hints on the State TypedDict).
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def build_cell_deps(cell_name: str, node_name: str, cell_config: dict) -> CellDeps:
    """Build CellDeps for the cell.

    Substrate ports + LLM clients are lazy-loaded:
    - checkpointer: MST sidecar via MST_CHECKPOINT_SOCKET env, else FileCheckpointSaver fallback
    - sdk / base / geth / pds / llm: scaffold (None for now; populated when modules exist)
    """
    # Checkpointer: prefer MST sidecar, fallback to file
    checkpointer = _build_checkpointer(cell_name)

    # TODO(ADR-2605202200 follow-up): wire sdk via @etzhayyim/sdk sidecar
    # TODO: wire base_l2_port + geth_private_port from deps.toml chain config
    # TODO: wire pds_client to pds.etzhayyim.com
    # TODO: wire llm_primary / llm_fallback_local via LiteLLM gateway (ADR-2605191358)

    return CellDeps(
        cell_name=cell_name,
        node_name=node_name,
        checkpointer=checkpointer,
        config=cell_config,
    )


def _build_checkpointer(cell_name: str):
    """Build checkpointer: prefer MST sidecar, fallback to file-based.

    Scaffold: returns None when neither is wired. Cells should tolerate
    None checkpointer during early bring-up (LangGraph default MemorySaver).
    """
    import os

    sidecar_socket = os.environ.get("MST_CHECKPOINT_SOCKET")
    if sidecar_socket:
        try:
            from kotodama.checkpointer import MstCheckpointSaver  # type: ignore

            return MstCheckpointSaver(socket_path=sidecar_socket)
        except ImportError:
            logger.warning("[%s] MstCheckpointSaver unavailable, falling back", cell_name)

    # File checkpointer fallback
    try:
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()
    except ImportError:
        logger.warning("[%s] no checkpointer available", cell_name)
        return None


class _HealthzHandler(BaseHTTPRequestHandler):
    """HTTP handler for /healthz endpoint."""

    cell_status_provider: Any = None  # set by serve_healthz

    def do_GET(self):  # noqa: N802 (BaseHTTPRequestHandler convention)
        if self.path != "/healthz":
            self.send_response(404)
            self.end_headers()
            return
        status = self.cell_status_provider() if self.cell_status_provider else None
        if status is None:
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":"status unavailable"}')
            return
        body = json.dumps(status.to_dict()).encode("utf-8")
        self.send_response(status.status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002 (override silence)
        # Silence default access log; rely on structured logging instead.
        pass


def serve_healthz(port: int, status_provider) -> threading.Thread:
    """Start healthz HTTP server on the given port.

    status_provider: callable returning a HealthzStatus instance.
    """
    _HealthzHandler.cell_status_provider = status_provider
    server = ThreadingHTTPServer(("127.0.0.1", port), _HealthzHandler)
    thread = threading.Thread(target=server.serve_forever, name=f"healthz:{port}", daemon=True)
    thread.start()
    logger.info("healthz listening on http://127.0.0.1:%d/healthz", port)
    return thread


def run_mst_listener_loop(
    cell_module: Any,
    graph: Any,
    deps: CellDeps,
    listens_to: list[str],
    shutdown_event: threading.Event,
) -> None:
    """Run the MST listener trigger loop.

    Scaffold: real MstListener integration is in ADR-2605171800 §Stage 1
    (separate PR). For now this loop blocks on shutdown_event and logs
    that it would subscribe to the given NSIDs.
    """
    logger.info(
        "[%s] mst-listener loop scaffold; would subscribe to: %s",
        deps.cell_name,
        ",".join(listens_to),
    )
    # TODO: wire kotodama.listener.MstListener once it's wired into PDS subscribeRepos
    while not shutdown_event.is_set():
        shutdown_event.wait(timeout=5.0)


def run_cron_loop(
    cell_module: Any,
    graph: Any,
    deps: CellDeps,
    cron_expr: str,
    shutdown_event: threading.Event,
) -> None:
    """Run a cron-style trigger loop using croniter.

    Scaffold: logs the cron schedule and waits. Real cron invocation
    drives `graph.invoke({}, config={"configurable": {"thread_id": ...}})`
    on each tick.
    """
    logger.info("[%s] cron loop scaffold; expr=%s", deps.cell_name, cron_expr)
    while not shutdown_event.is_set():
        shutdown_event.wait(timeout=60.0)


def run_synchronous_api_loop(
    cell_module: Any,
    graph: Any,
    deps: CellDeps,
    api_port: int,
    shutdown_event: threading.Event,
) -> None:
    """Run a synchronous-API trigger loop (HTTP POST → invoke → response).

    Scaffold: opens the port and blocks on shutdown. Real implementation
    handles POST /<cell>/invoke with request body as initial state.
    """
    logger.info("[%s] synchronous-api loop scaffold; port=%d", deps.cell_name, api_port)
    while not shutdown_event.is_set():
        shutdown_event.wait(timeout=5.0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cell-host")
    parser.add_argument("--cell", required=True, help="Cell name (CamelCase, e.g. SiteSurveyCell)")
    parser.add_argument("--node", required=True, help="Murakumo node name")
    parser.add_argument("--healthz-port", type=int, required=True)
    parser.add_argument("--listens-to", action="append", default=[], help="NSID(s) to subscribe (repeatable)")
    parser.add_argument("--trigger", required=True, choices=["mst-listener", "cron", "synchronous-api", "mst-listener + heartbeat-monitor", "cron + mst-listener", "timer + mst-listener", "mst-listener + escalation from other cells", "continuous + super-step boundary + event-driven"])
    parser.add_argument("--cron", default="", help="Cron expression (when trigger=cron)")
    parser.add_argument("--api-port", type=int, default=0, help="API port (when trigger=synchronous-api)")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s [%(threadName)s]: %(message)s",
    )

    logger.info("starting cell-host for cell=%s node=%s", args.cell, args.node)

    # Import cell module
    try:
        cell_module = import_cell_module(args.cell)
    except (FileNotFoundError, ImportError) as e:
        logger.error("failed to import cell module: %s", e)
        return 2

    # Verify contract symbols
    missing = [
        sym for sym in ("build_graph", "state_from_event", "thread_id_from_event")
        if not hasattr(cell_module, sym)
    ]
    if missing:
        # Legacy cells may not export state_from_event / thread_id_from_event yet.
        # Per ADR-2605202200 §9 Phase A: adapter falls back to defaults.
        for sym in missing:
            if sym == "state_from_event":
                cell_module.state_from_event = default_state_from_event
            elif sym == "thread_id_from_event":
                cell_module.thread_id_from_event = default_thread_id_from_event
            else:
                logger.error("cell %s missing required symbol %s", args.cell, sym)
                return 3

    # Build dependencies (fleet.toml cell config would be passed in via env or arg in full impl)
    deps = build_cell_deps(args.cell, args.node, cell_config={})

    # Optional startup hook
    if hasattr(cell_module, "on_startup"):
        try:
            cell_module.on_startup(deps)
        except Exception:
            logger.exception("on_startup raised")

    # Build the graph. Three call signatures are tolerated (per
    # ADR-2605202200 + ADR-2605232100):
    #   (a) New contract:    build_graph(deps)
    #   (b) Legacy 1-arg:    build_graph(checkpointer)
    #   (c) Legacy multi-arg: build_graph(checkpointer, *port_objects)
    # The multi-arg cells (charter / land / treasury / etc.) accept None
    # for missing ports — cells degrade gracefully when substrate ports
    # are not yet wired into CellDeps.
    try:
        graph = cell_module.build_graph(deps)
    except TypeError:
        try:
            logger.info("[%s] using legacy build_graph(checkpointer, ...) adapter", args.cell)
            graph = cell_module.build_graph(deps.checkpointer)  # type: ignore[misc]
        except TypeError as e:
            # Multi-arg legacy. Inspect the cell's signature and best-effort
            # populate from CellDeps fields. Any unknown parameter stays None.
            import inspect

            sig = inspect.signature(cell_module.build_graph)
            kwargs: dict[str, Any] = {}
            for param_name in sig.parameters:
                if param_name == "checkpointer":
                    kwargs[param_name] = deps.checkpointer
                elif param_name in ("llm_client", "llm_primary"):
                    kwargs[param_name] = getattr(deps, "llm_primary", None)
                elif param_name in ("llm_fallback", "llm_local"):
                    kwargs[param_name] = getattr(deps, "llm_fallback_local", None)
                elif param_name in ("base_port", "base_l2_port"):
                    kwargs[param_name] = getattr(deps, "base_l2_port", None)
                elif param_name in ("geth_port", "geth_private_port"):
                    kwargs[param_name] = getattr(deps, "geth_private_port", None)
                elif param_name == "pds_port":
                    kwargs[param_name] = getattr(deps, "pds_client", None)
                elif param_name == "sdk":
                    kwargs[param_name] = getattr(deps, "sdk", None)
                else:
                    # Unknown port (council_dispatcher / charter_registry_port /
                    # treasury_port / etc.) — cell-side default kwarg handles this.
                    kwargs[param_name] = None
            logger.info(
                "[%s] using legacy multi-arg build_graph adapter: %s",
                args.cell,
                {k: ("set" if v is not None else "None") for k, v in kwargs.items()},
            )
            graph = cell_module.build_graph(**kwargs)

    # Shutdown coordination
    shutdown_event = threading.Event()
    start_time = time.time()

    # Healthz
    def status_provider() -> HealthzStatus:
        extra = {}
        if hasattr(cell_module, "healthz_extra"):
            try:
                extra = cell_module.healthz_extra(deps)
            except Exception:
                logger.exception("healthz_extra raised")
        return HealthzStatus(
            cell=args.cell,
            node=args.node,
            uptime_seconds=time.time() - start_time,
            trigger=args.trigger,
            listens_to=list(args.listens_to),
            checkpointer_type="mst" if hasattr(deps.checkpointer, "socket_path") else (
                "file" if deps.checkpointer is not None else "none"
            ),
            checkpointer_ok=deps.checkpointer is not None,
            checkpointer_last_write_seconds_ago=None,
            swarm_role="unknown",  # TODO: integrate ADR-2605191603
            witness_min=deps.config.get("witness_min"),
            cell_extra=extra,
        )

    serve_healthz(args.healthz_port, status_provider)

    # Signal handlers
    def handle_sigterm(signum, frame):
        logger.info("[%s] shutdown signal received (%d)", args.cell, signum)
        shutdown_event.set()

    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)

    # Trigger dispatch
    trigger = args.trigger
    if "mst-listener" in trigger:
        run_mst_listener_loop(cell_module, graph, deps, args.listens_to, shutdown_event)
    elif "cron" in trigger and args.cron:
        run_cron_loop(cell_module, graph, deps, args.cron, shutdown_event)
    elif "synchronous" in trigger and args.api_port:
        run_synchronous_api_loop(cell_module, graph, deps, args.api_port, shutdown_event)
    else:
        logger.warning("[%s] unrecognised trigger '%s' — idling until shutdown", args.cell, trigger)
        while not shutdown_event.is_set():
            shutdown_event.wait(timeout=10.0)

    # Graceful shutdown
    if hasattr(cell_module, "on_shutdown"):
        try:
            cell_module.on_shutdown(deps)
        except Exception:
            logger.exception("on_shutdown raised")

    logger.info("[%s] cell-host exiting", args.cell)
    return 0


if __name__ == "__main__":
    sys.exit(main())
