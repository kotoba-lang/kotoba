"""
KuniUmiApiCell — HTTP gateway for the 6 kuni-umi cells.

Per ADR-2605201400 + ADR-2605192415 §4. This cell is the front door that
the ``etzhayyim kuni-umi`` CLI POSTs into. Each XRPC NSID is routed to the
corresponding kuni-umi cell module:

  defineDeploymentSite          → site_survey.cell
  submitSiteSurvey              → site_survey.cell
  proposeDeploymentPlan         → deployment_planning.cell
  recordConstructionProgress    → construction_orchestration.cell
  commissionDeployment          → commissioning.cell
  recordPhysicalAuditEvent      → audit_witness.cell

The cell-runner trigger kind is ``lan-api`` (same as
UnispscAgentExecutorCell — see ``_spawn_lan_api_cell`` in
``kotodama.cell_runner_main``). Endpoints (POST unless noted):

  GET  /healthz                                                → service health
  GET  /lexicons                                               → mounted NSIDs
  POST /xrpc/{nsid}                                            → canonical XRPC
  POST /api/{lexicon-name}                                     → camelCase alias
  POST /api/invoke                                             → CLI back-compat

Dev mode (``KUNI_UMI_API_DEV_MODE=1``, default true) skips the MST
roundtrip and invokes the LangGraph directly. When disabled the cell
returns 501 ``ProductionWiringPending`` until the PdsClient integration
lands.

Co-resident on ``naphtali`` per ADR-2605201400 §1 (same node as the
SiteSurvey leader — keeps kuni-umi locally hot).
"""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

from aiohttp import web

try:
    from langgraph.errors import GraphRecursionError
except ImportError:  # pragma: no cover — older langgraph
    class GraphRecursionError(Exception):  # type: ignore[no-redef]
        pass

logger = logging.getLogger("KuniUmiApiCell")

# Cells live one level up from this file (cells/kuni_umi_api/ ↔ cells/*/).
_CELLS_DIR = Path(__file__).resolve().parent.parent

# ── Routing table ──────────────────────────────────────────────────────

LEXICON_TO_CELL_MAP: dict[str, tuple[str, str]] = {
    "com.etzhayyim.apps.etzhayyim.kuniUmi.defineDeploymentSite": (
        "site_survey.cell",
        "define_site",
    ),
    "com.etzhayyim.apps.etzhayyim.kuniUmi.submitSiteSurvey": (
        "site_survey.cell",
        "submit_survey",
    ),
    "com.etzhayyim.apps.etzhayyim.kuniUmi.proposeDeploymentPlan": (
        "deployment_planning.cell",
        "propose_plan",
    ),
    "com.etzhayyim.apps.etzhayyim.kuniUmi.recordConstructionProgress": (
        "construction_orchestration.cell",
        "record_progress",
    ),
    "com.etzhayyim.apps.etzhayyim.kuniUmi.commissionDeployment": (
        "commissioning.cell",
        "commission",
    ),
    "com.etzhayyim.apps.etzhayyim.kuniUmi.recordPhysicalAuditEvent": (
        "audit_witness.cell",
        "audit_event",
    ),
}

# NSIDs that the lexicons require ≥2 witness attestations on (mirror the
# lexicon `minItems: 2` constraint to fail fast at the gateway boundary).
WITNESS_REQUIRED_NSIDS: frozenset[str] = frozenset({
    "com.etzhayyim.apps.etzhayyim.kuniUmi.submitSiteSurvey",
    "com.etzhayyim.apps.etzhayyim.kuniUmi.recordConstructionProgress",
    "com.etzhayyim.apps.etzhayyim.kuniUmi.recordPhysicalAuditEvent",
})

WITNESS_MIN = 2  # constitutional invariant — never reduce

NSID_PREFIX = "com.etzhayyim.apps.etzhayyim.kuniUmi."

# Cap LangGraph traversal so the witness fixed-point cannot spin forever
# when the body supplies zero attestations and dev-mode is on.
GRAPH_RECURSION_LIMIT = 100


# ── In-process state ──────────────────────────────────────────────────


class _Mounted:
    """Per-process mount registry.

    Holds the lazily-resolved cell module reference plus a cached graph
    handle so repeated invocations reuse the same compiled StateGraph.
    """

    def __init__(self, module_path: str, input_kind: str):
        self.module_path = module_path
        self.input_kind = input_kind
        self.module: Any | None = None
        self.graph: Any | None = None
        self.import_error: str | None = None

    def ensure_loaded(self) -> bool:
        if self.module is not None and self.graph is not None:
            return True
        if self.import_error is not None:
            return False
        try:
            mod = importlib.import_module(self.module_path)
        except Exception as exc:  # noqa: BLE001
            self.import_error = f"import {self.module_path}: {exc}"
            logger.warning("KuniUmiApiCell %s", self.import_error)
            return False
        graph = getattr(mod, "graph", None)
        if graph is None:
            self.import_error = f"{self.module_path} has no `graph` attribute"
            return False
        self.module = mod
        self.graph = graph
        return True


class _GatewayState:
    def __init__(self) -> None:
        self.started_at = time.time()
        self.invoke_count = 0
        self.invoke_errors = 0
        self.mounted: dict[str, _Mounted] = {}
        self.dev_mode: bool = _dev_mode_default()

    def mount_all(self) -> list[str]:
        ok: list[str] = []
        for nsid, (module_path, input_kind) in LEXICON_TO_CELL_MAP.items():
            m = _Mounted(module_path, input_kind)
            self.mounted[nsid] = m
            if m.ensure_loaded():
                ok.append(nsid)
            else:
                logger.warning(
                    "KuniUmiApiCell: %s failed to mount (%s)",
                    nsid,
                    m.import_error,
                )
        return ok


def _dev_mode_default() -> bool:
    raw = os.environ.get("KUNI_UMI_API_DEV_MODE")
    if raw is None:
        return os.environ.get("ETZHAYYIM_ENV", "").lower() != "production"
    return raw.strip().lower() in ("1", "true", "yes", "on")


# ── Helpers ───────────────────────────────────────────────────────────


def _ensure_cells_on_path() -> None:
    """Make `import site_survey.cell` etc. work — cells dir on sys.path."""
    cells_str = str(_CELLS_DIR)
    if cells_str not in sys.path:
        sys.path.insert(0, cells_str)


def _short_nsid(nsid: str) -> str:
    return nsid[len(NSID_PREFIX):] if nsid.startswith(NSID_PREFIX) else nsid


def _validate_witnesses(nsid: str, body: dict[str, Any]) -> str | None:
    if nsid not in WITNESS_REQUIRED_NSIDS:
        return None
    sigs = body.get("witnessAttestations")
    if not isinstance(sigs, list) or len(sigs) < WITNESS_MIN:
        return (
            f"WitnessQuorumNotMet: {nsid} requires "
            f">= {WITNESS_MIN} witnessAttestations (got "
            f"{len(sigs) if isinstance(sigs, list) else 0})"
        )
    return None


def _validate_define_site_geo(body: dict[str, Any]) -> str | None:
    """defineDeploymentSite.geo is a GeoJSON Feature (lexicon-declared as
    string). Accept either a JSON-string OR a pre-parsed object.
    """
    geo = body.get("geo")
    if geo is None:
        return None
    if isinstance(geo, dict):
        return None
    if isinstance(geo, str):
        try:
            json.loads(geo)
        except json.JSONDecodeError as exc:
            return f"InvalidGeoJSON: {exc}"
        return None
    return "InvalidGeoJSON: geo must be a JSON string or object"


def _event_from_body(nsid: str, body: dict[str, Any]) -> dict[str, Any]:
    repo = (
        body.get("siteDid")
        or body.get("planDid")
        or body.get("repo")
        or ""
    )
    return {
        "uri": f"kuni-umi-api://{nsid}",
        "record": body,
        "value": body,
        "repo": repo,
    }


def _coerce_state(
    mount: _Mounted,
    nsid: str,
    event: dict[str, Any],
    body: dict[str, Any],
) -> dict[str, Any]:
    """Build the initial LangGraph state.

    Prefers the cell module's own ``state_from_event`` (each kuni-umi cell
    provides one). If it returns nothing for a field that the body
    supplies, fold the body value in so the CLI's flat-payload shape still
    reaches the graph.

    ``defineDeploymentSite`` shares the SiteSurveyCell graph with
    ``submitSiteSurvey``, but its lexicon does NOT carry witness
    attestations (it is a synchronous jurisdiction DMN per ADR-2605201400
    §5). To prevent the witness fixed-point from blocking the define-site
    path indefinitely, we pre-seed two synthetic gateway attestations
    when the NSID is defineDeploymentSite. submitSiteSurvey continues to
    require real witnesses (enforced by _validate_witnesses above).
    """
    state: dict[str, Any] = {}
    state_fn = getattr(mount.module, "state_from_event", None)
    if callable(state_fn):
        try:
            seeded = state_fn(event)
            if isinstance(seeded, dict):
                state.update(seeded)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "KuniUmiApiCell %s: state_from_event raised %s — falling back to raw body",
                mount.module_path,
                exc,
            )
    # Make sure the raw body is available under a stable key for cells
    # that prefer to read it directly.
    state.setdefault("input_body", body)

    if nsid == "com.etzhayyim.apps.etzhayyim.kuniUmi.defineDeploymentSite":
        # The define-site lexicon does not model witnesses — seed the
        # graph quorum input so the synchronous DMN run can terminate.
        gateway_witnesses = [
            {"signer": "kuni-umi-api-gateway", "sig": "synthetic-define-site-1"},
            {"signer": "kuni-umi-api-gateway", "sig": "synthetic-define-site-2"},
        ]
        existing = state.get("witness_attestations")
        if not isinstance(existing, list) or len(existing) < WITNESS_MIN:
            state["witness_attestations"] = gateway_witnesses

    return state


def _thread_id(mount: _Mounted, nsid: str, event: dict[str, Any]) -> str:
    fn = getattr(mount.module, "thread_id_from_event", None)
    if callable(fn):
        try:
            tid = fn(event)
            if isinstance(tid, str) and tid:
                return tid
        except Exception:  # noqa: BLE001
            pass
    return f"kuni-umi-api-{_short_nsid(nsid)}-{int(time.time() * 1000)}"


# ── HTTP handlers ─────────────────────────────────────────────────────


def _bind_handlers(app: web.Application, gw: _GatewayState) -> None:
    app["gw"] = gw

    async def healthz(_request: web.Request) -> web.Response:
        mounted = [nsid for nsid, m in gw.mounted.items() if m.graph is not None]
        return web.json_response({
            "ok": True,
            "service": "KuniUmiApiCell",
            "mountedLexicons": mounted,
            "mountFailures": {
                nsid: m.import_error
                for nsid, m in gw.mounted.items()
                if m.import_error
            },
            "devMode": gw.dev_mode,
            "witnessMin": WITNESS_MIN,
            "uptimeS": int(time.time() - gw.started_at),
            "invokeCount": gw.invoke_count,
            "invokeErrors": gw.invoke_errors,
        })

    async def list_lexicons(_request: web.Request) -> web.Response:
        return web.json_response({
            "ok": True,
            "lexicons": list(LEXICON_TO_CELL_MAP.keys()),
        })

    async def dispatch_nsid(nsid: str, request: web.Request) -> web.Response:
        if nsid not in LEXICON_TO_CELL_MAP:
            return web.json_response(
                {"ok": False, "error": "UnknownLexicon", "nsid": nsid},
                status=404,
            )
        mount = gw.mounted.get(nsid)
        if mount is None or not mount.ensure_loaded():
            gw.invoke_errors += 1
            return web.json_response(
                {
                    "ok": False,
                    "error": "CellImportFailed",
                    "nsid": nsid,
                    "detail": (mount.import_error if mount else "not mounted"),
                },
                status=500,
            )
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return web.json_response(
                {"ok": False, "error": "InvalidJSON"}, status=400
            )
        if not isinstance(body, dict):
            return web.json_response(
                {"ok": False, "error": "BodyMustBeObject"}, status=400
            )

        witness_err = _validate_witnesses(nsid, body)
        if witness_err:
            return web.json_response(
                {
                    "ok": False,
                    "error": "WitnessQuorumNotMet",
                    "nsid": nsid,
                    "detail": witness_err,
                },
                status=400,
            )

        if nsid == "com.etzhayyim.apps.etzhayyim.kuniUmi.defineDeploymentSite":
            geo_err = _validate_define_site_geo(body)
            if geo_err:
                return web.json_response(
                    {
                        "ok": False,
                        "error": "InvalidGeoJSON",
                        "nsid": nsid,
                        "detail": geo_err,
                    },
                    status=400,
                )

        if not gw.dev_mode:
            return web.json_response(
                {
                    "ok": False,
                    "error": "ProductionWiringPending",
                    "nsid": nsid,
                    "detail": (
                        "PdsClient integration not yet wired — set "
                        "KUNI_UMI_API_DEV_MODE=1 to invoke the cell graph "
                        "directly"
                    ),
                },
                status=501,
            )

        event = _event_from_body(nsid, body)
        state = _coerce_state(mount, nsid, event, body)
        thread_id = _thread_id(mount, nsid, event)
        config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": "",
            },
            "recursion_limit": GRAPH_RECURSION_LIMIT,
        }

        t0 = time.perf_counter()
        loop = asyncio.get_running_loop()
        try:
            terminal = await loop.run_in_executor(
                None,
                lambda: mount.graph.invoke(state, config=config),
            )
        except GraphRecursionError as exc:
            gw.invoke_errors += 1
            logger.warning(
                "KuniUmiApiCell %s: recursion limit hit (likely awaiting witnesses): %s",
                nsid,
                exc,
            )
            return web.json_response(
                {
                    "ok": False,
                    "error": "AwaitingWitnessQuorum",
                    "nsid": nsid,
                    "threadId": thread_id,
                    "detail": (
                        "graph paused at witness fixed-point — supply "
                        ">=2 witnessAttestations to advance"
                    ),
                },
                status=202,
            )
        except Exception as exc:  # noqa: BLE001
            gw.invoke_errors += 1
            logger.exception("KuniUmiApiCell %s: invoke failed", nsid)
            return web.json_response(
                {
                    "ok": False,
                    "error": "InvokeException",
                    "nsid": nsid,
                    "threadId": thread_id,
                    "detail": str(exc),
                },
                status=500,
            )
        finally:
            gw.invoke_count += 1
        latency_ms = (time.perf_counter() - t0) * 1000
        state_out = terminal if isinstance(terminal, dict) else {"value": terminal}
        return web.json_response({
            "ok": True,
            "nsid": nsid,
            "threadId": thread_id,
            "state": state_out,
            "latencyMs": round(latency_ms, 2),
        })

    async def xrpc_handler(request: web.Request) -> web.Response:
        nsid = request.match_info["nsid"]
        return await dispatch_nsid(nsid, request)

    async def api_alias_handler(request: web.Request) -> web.Response:
        short = request.match_info["short"]
        nsid = f"{NSID_PREFIX}{short}"
        return await dispatch_nsid(nsid, request)

    async def api_invoke_handler(request: web.Request) -> web.Response:
        """Back-compat for the CLI's default `/api/invoke` target.

        Body must include either `_nsid` or `lexicon` naming the target.
        """
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return web.json_response(
                {"ok": False, "error": "InvalidJSON"}, status=400
            )
        if not isinstance(body, dict):
            return web.json_response(
                {"ok": False, "error": "BodyMustBeObject"}, status=400
            )
        target = body.pop("_nsid", None) or body.pop("lexicon", None)
        if not isinstance(target, str) or not target:
            return web.json_response(
                {
                    "ok": False,
                    "error": "MissingNSID",
                    "detail": "POST /api/invoke requires `_nsid` or `lexicon` field",
                },
                status=400,
            )
        if "." not in target:
            target = f"{NSID_PREFIX}{target}"

        # Re-pack a Request-like wrapper isn't worth it — dispatch directly
        # by recreating the body fetch path.
        nsid = target
        if nsid not in LEXICON_TO_CELL_MAP:
            return web.json_response(
                {"ok": False, "error": "UnknownLexicon", "nsid": nsid},
                status=404,
            )
        mount = gw.mounted.get(nsid)
        if mount is None or not mount.ensure_loaded():
            gw.invoke_errors += 1
            return web.json_response(
                {
                    "ok": False,
                    "error": "CellImportFailed",
                    "nsid": nsid,
                    "detail": (mount.import_error if mount else "not mounted"),
                },
                status=500,
            )

        witness_err = _validate_witnesses(nsid, body)
        if witness_err:
            return web.json_response(
                {
                    "ok": False,
                    "error": "WitnessQuorumNotMet",
                    "nsid": nsid,
                    "detail": witness_err,
                },
                status=400,
            )
        if nsid == "com.etzhayyim.apps.etzhayyim.kuniUmi.defineDeploymentSite":
            geo_err = _validate_define_site_geo(body)
            if geo_err:
                return web.json_response(
                    {
                        "ok": False,
                        "error": "InvalidGeoJSON",
                        "nsid": nsid,
                        "detail": geo_err,
                    },
                    status=400,
                )
        if not gw.dev_mode:
            return web.json_response(
                {
                    "ok": False,
                    "error": "ProductionWiringPending",
                    "nsid": nsid,
                },
                status=501,
            )

        event = _event_from_body(nsid, body)
        state = _coerce_state(mount, nsid, event, body)
        thread_id = _thread_id(mount, nsid, event)
        config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": "",
            },
            "recursion_limit": GRAPH_RECURSION_LIMIT,
        }
        t0 = time.perf_counter()
        loop = asyncio.get_running_loop()
        try:
            terminal = await loop.run_in_executor(
                None,
                lambda: mount.graph.invoke(state, config=config),
            )
        except GraphRecursionError as exc:
            gw.invoke_errors += 1
            return web.json_response(
                {
                    "ok": False,
                    "error": "AwaitingWitnessQuorum",
                    "nsid": nsid,
                    "threadId": thread_id,
                    "detail": str(exc),
                },
                status=202,
            )
        except Exception as exc:  # noqa: BLE001
            gw.invoke_errors += 1
            logger.exception("KuniUmiApiCell %s: invoke failed", nsid)
            return web.json_response(
                {
                    "ok": False,
                    "error": "InvokeException",
                    "nsid": nsid,
                    "threadId": thread_id,
                    "detail": str(exc),
                },
                status=500,
            )
        finally:
            gw.invoke_count += 1
        latency_ms = (time.perf_counter() - t0) * 1000
        state_out = terminal if isinstance(terminal, dict) else {"value": terminal}
        return web.json_response({
            "ok": True,
            "nsid": nsid,
            "threadId": thread_id,
            "state": state_out,
            "latencyMs": round(latency_ms, 2),
        })

    app.router.add_get("/healthz", healthz)
    app.router.add_get("/lexicons", list_lexicons)
    app.router.add_post("/xrpc/{nsid}", xrpc_handler)
    app.router.add_post("/api/invoke", api_invoke_handler)
    app.router.add_post("/api/{short}", api_alias_handler)


# ── cell-runner contract ──────────────────────────────────────────────


def healthz() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "KuniUmiApiCell",
        "mountedLexicons": list(LEXICON_TO_CELL_MAP),
    }


async def serve(stop_event: asyncio.Event, healthz_port: int, api_port: int) -> None:
    _ensure_cells_on_path()
    gw = _GatewayState()
    mounted = gw.mount_all()
    logger.info(
        "KuniUmiApiCell mounted %d/%d lexicons (devMode=%s)",
        len(mounted),
        len(LEXICON_TO_CELL_MAP),
        gw.dev_mode,
    )

    app = web.Application()
    _bind_handlers(app, gw)

    runner = web.AppRunner(app)
    await runner.setup()
    sites = [web.TCPSite(runner, "0.0.0.0", api_port)]
    if healthz_port != api_port:
        sites.append(web.TCPSite(runner, "0.0.0.0", healthz_port))
    for site in sites:
        await site.start()
    logger.info(
        "KuniUmiApiCell serving 0.0.0.0:%d (healthz=%d) — %d lexicons live",
        api_port,
        healthz_port,
        len(mounted),
    )
    try:
        await stop_event.wait()
    finally:
        await runner.cleanup()
        logger.info("KuniUmiApiCell shut down")


__all__ = [
    "LEXICON_TO_CELL_MAP",
    "WITNESS_REQUIRED_NSIDS",
    "WITNESS_MIN",
    "NSID_PREFIX",
    "healthz",
    "serve",
]
