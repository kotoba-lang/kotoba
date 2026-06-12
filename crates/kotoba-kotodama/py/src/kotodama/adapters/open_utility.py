"""
open-utility CIM adapter — kuni-umi → open-* utility bridge.

Per ADR-2605201400 §1 (orchestration seam between kuni-umi Pregel cells —
CommissioningCell + ConstructionOrchestrationCell — and the 10 open-* utility
apps: open-{denki,gas,water,network,power,rail,airplane,ports,robo,ot}).

This is the seam through which kuni-umi (transient orchestration) hands off
steady-state control to the open-* utility apps (persistent operators). The
critical handoff target is `define_loop` (open-ot WASM PLC), which honors
ADR-2605201400 §3 P3: "kuni-umi never drives hard-RT motion" — cadence_hz
above 10 Hz is rejected unless an explicit override env var is set.

Adapter mode (env `OPEN_UTILITY_ADAPTER_MODE`):
  * "stub"     — return synthetic DID + structured log only (DEFAULT, this iteration).
  * "lan-http" — POST to the open-* app's LAN endpoint (next phase, not implemented).
  * "xrpc"     — POST to https://{nanoid}.etzhayyim.com/xrpc/... (production,
                 not implemented).

Stdlib only. No `requests`/`aiohttp` (per task constraints). Callers chain on
the returned `CimRecord` (or `dict`) using `.did`.
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("kotodama.adapters.open_utility")


# ---------------------------------------------------------------------------
# Module config
# ---------------------------------------------------------------------------

#: Adapter mode. Only "stub" is wired in this iteration.
ADAPTER_MODE = os.environ.get("OPEN_UTILITY_ADAPTER_MODE", "stub")

#: Base DID prefix for all synthetic records (root authority lives at
#: did:web:etzhayyim.com per CLAUDE.md identity rules).
DID_PREFIX = "did:web:etzhayyim.com"

#: Maximum cadence_hz allowed when kuni-umi is the source of an open-ot loop.
#: Per ADR-2605201400 §3 P3, kuni-umi must NEVER drive hard-RT motion.
KUNI_UMI_CADENCE_LIMIT_HZ = 10.0

#: Override env var. When set to "1", `define_loop` bypasses the cadence
#: ceiling — reserved for non-kuni-umi callers (e.g. dedicated open-ot
#: deployment scripts that explicitly own the SIL boundary).
ALLOW_HIGH_CADENCE_ENV = "OPEN_UTILITY_ALLOW_HIGH_CADENCE"

#: Tuple of open-* apps this adapter can speak to.
SUPPORTED_APPS: tuple[str, ...] = (
    "open-denki",
    "open-gas",
    "open-water",
    "open-network",
    "open-ot",
    "open-robo",
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CimRecord:
    """A single CIM (Common Information Model) record echoed back to the caller.

    Callers should chain by reading `.did`. `ok=False` records carry the
    failure reason in `detail["error"]` and DO have a synthetic DID (so trace
    correlation still works), but callers MUST honor `.ok` before chaining.
    """

    did: str
    app: str
    record_kind: str
    ok: bool
    stubbed: bool
    created_at: str
    detail: dict[str, Any] | None = field(default=None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "did": self.did,
            "app": self.app,
            "recordKind": self.record_kind,
            "ok": self.ok,
            "stubbed": self.stubbed,
            "createdAt": self.created_at,
            "detail": self.detail or {},
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SLUG_RX = re.compile(r"[^a-z0-9-]+")
_WS_RX = re.compile(r"\s+")


def _slugify(name: str) -> str:
    """Lowercase, replace whitespace with `-`, strip non-[a-z0-9-]. Empty
    inputs return "" so callers can fall through to a uuid stem."""
    if not name:
        return ""
    s = name.strip().lower()
    s = _WS_RX.sub("-", s)
    s = _SLUG_RX.sub("", s)
    s = s.strip("-")
    return s


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mint_did(app: str, record_kind: str, name: str) -> str:
    stem = _slugify(name) or uuid.uuid4().hex[:8]
    return f"{DID_PREFIX}:{app}:{record_kind}:{stem}"


def _missing(field_name: str, app: str, record_kind: str) -> CimRecord:
    """Build a uniform validation-failure record."""
    return CimRecord(
        did=f"{DID_PREFIX}:{app}:{record_kind}:invalid:{uuid.uuid4().hex[:8]}",
        app=app,
        record_kind=record_kind,
        ok=False,
        stubbed=True,
        created_at=_utcnow_iso(),
        detail={"error": f"Missing{field_name}"},
    )


def _stub(
    *,
    app: str,
    record_kind: str,
    name: str,
    detail: dict[str, Any],
) -> CimRecord:
    """Mint a synthetic CIM record, log it, and return."""
    did = _mint_did(app, record_kind, name)
    rec = CimRecord(
        did=did,
        app=app,
        record_kind=record_kind,
        ok=True,
        stubbed=True,
        created_at=_utcnow_iso(),
        detail=detail,
    )
    logger.info(
        "open-utility stub: app=%s kind=%s did=%s kwargs=%s",
        app,
        record_kind,
        did,
        detail,
    )
    return rec


# ---------------------------------------------------------------------------
# open-denki — electric grid
# ---------------------------------------------------------------------------


def define_generation_node(
    *,
    site_did: str,
    name: str,
    capacity_kw: float,
    source_kind: str = "solar",
    steward_did: str = "",
) -> CimRecord:
    """Register a generation node (solar array, gen-set, micro-hydro, ...)."""
    app, kind = "open-denki", "generation-node"
    if not site_did:
        return _missing("SiteDid", app, kind)
    if not name:
        return _missing("Name", app, kind)
    if capacity_kw is None:
        return _missing("CapacityKw", app, kind)
    return _stub(
        app=app,
        record_kind=kind,
        name=name,
        detail={
            "siteDid": site_did,
            "name": name,
            "capacityKw": float(capacity_kw),
            "sourceKind": source_kind,
            "stewardDid": steward_did,
        },
    )


def define_substation(
    *,
    site_did: str,
    name: str,
    voltage_kv: float,
    upstream_node_dids: list[str] | None = None,
) -> CimRecord:
    """Register a substation (steps down from generation/feeder voltage)."""
    app, kind = "open-denki", "substation"
    if not site_did:
        return _missing("SiteDid", app, kind)
    if not name:
        return _missing("Name", app, kind)
    if voltage_kv is None:
        return _missing("VoltageKv", app, kind)
    return _stub(
        app=app,
        record_kind=kind,
        name=name,
        detail={
            "siteDid": site_did,
            "name": name,
            "voltageKv": float(voltage_kv),
            "upstreamNodeDids": list(upstream_node_dids or []),
        },
    )


def define_feeder(
    *,
    site_did: str,
    substation_did: str,
    voltage_kv: float,
    length_m: float,
    conductor_spec: str = "ACSR",
) -> CimRecord:
    """Register a distribution feeder leaving a substation."""
    app, kind = "open-denki", "feeder"
    if not site_did:
        return _missing("SiteDid", app, kind)
    if not substation_did:
        return _missing("SubstationDid", app, kind)
    if voltage_kv is None:
        return _missing("VoltageKv", app, kind)
    if length_m is None:
        return _missing("LengthM", app, kind)
    # Feeders rarely have human-meaningful names; mint from substation+voltage.
    name = f"feeder-{_slugify(substation_did.split(':')[-1])}-{voltage_kv}kv"
    return _stub(
        app=app,
        record_kind=kind,
        name=name,
        detail={
            "siteDid": site_did,
            "substationDid": substation_did,
            "voltageKv": float(voltage_kv),
            "lengthM": float(length_m),
            "conductorSpec": conductor_spec,
        },
    )


def register_smart_meter(
    *,
    feeder_did: str,
    household_did: str,
    meter_serial: str = "",
) -> CimRecord:
    """Bind a smart meter to a (feeder, household) pair."""
    app, kind = "open-denki", "smart-meter"
    if not feeder_did:
        return _missing("FeederDid", app, kind)
    if not household_did:
        return _missing("HouseholdDid", app, kind)
    serial = meter_serial or f"sm-{uuid.uuid4().hex[:10]}"
    return _stub(
        app=app,
        record_kind=kind,
        name=serial,
        detail={
            "feederDid": feeder_did,
            "householdDid": household_did,
            "meterSerial": serial,
        },
    )


# ---------------------------------------------------------------------------
# open-gas
# ---------------------------------------------------------------------------


def define_regulator(
    *,
    site_did: str,
    name: str,
    inlet_pressure_kpa: float,
    outlet_pressure_kpa: float,
) -> CimRecord:
    """Register a gas pressure regulator station."""
    app, kind = "open-gas", "regulator"
    if not site_did:
        return _missing("SiteDid", app, kind)
    if not name:
        return _missing("Name", app, kind)
    if inlet_pressure_kpa is None:
        return _missing("InletPressureKpa", app, kind)
    if outlet_pressure_kpa is None:
        return _missing("OutletPressureKpa", app, kind)
    return _stub(
        app=app,
        record_kind=kind,
        name=name,
        detail={
            "siteDid": site_did,
            "name": name,
            "inletPressureKpa": float(inlet_pressure_kpa),
            "outletPressureKpa": float(outlet_pressure_kpa),
        },
    )


def define_pipe_segment(
    *,
    regulator_did: str,
    name: str,
    length_m: float,
    diameter_mm: int,
) -> CimRecord:
    """Register a gas pipe segment downstream of a regulator."""
    app, kind = "open-gas", "pipe-segment"
    if not regulator_did:
        return _missing("RegulatorDid", app, kind)
    if not name:
        return _missing("Name", app, kind)
    if length_m is None:
        return _missing("LengthM", app, kind)
    if diameter_mm is None:
        return _missing("DiameterMm", app, kind)
    return _stub(
        app=app,
        record_kind=kind,
        name=name,
        detail={
            "regulatorDid": regulator_did,
            "name": name,
            "lengthM": float(length_m),
            "diameterMm": int(diameter_mm),
        },
    )


# ---------------------------------------------------------------------------
# open-water
# ---------------------------------------------------------------------------


def define_reservoir(
    *,
    site_did: str,
    name: str,
    capacity_kl: float,
    elevation_m: float = 0.0,
) -> CimRecord:
    """Register a water reservoir or tank."""
    app, kind = "open-water", "reservoir"
    if not site_did:
        return _missing("SiteDid", app, kind)
    if not name:
        return _missing("Name", app, kind)
    if capacity_kl is None:
        return _missing("CapacityKl", app, kind)
    return _stub(
        app=app,
        record_kind=kind,
        name=name,
        detail={
            "siteDid": site_did,
            "name": name,
            "capacityKl": float(capacity_kl),
            "elevationM": float(elevation_m),
        },
    )


def define_main(
    *,
    reservoir_did: str,
    name: str,
    length_m: float,
    diameter_mm: int,
) -> CimRecord:
    """Register a water distribution main downstream of a reservoir."""
    app, kind = "open-water", "main"
    if not reservoir_did:
        return _missing("ReservoirDid", app, kind)
    if not name:
        return _missing("Name", app, kind)
    if length_m is None:
        return _missing("LengthM", app, kind)
    if diameter_mm is None:
        return _missing("DiameterMm", app, kind)
    return _stub(
        app=app,
        record_kind=kind,
        name=name,
        detail={
            "reservoirDid": reservoir_did,
            "name": name,
            "lengthM": float(length_m),
            "diameterMm": int(diameter_mm),
        },
    )


# ---------------------------------------------------------------------------
# open-network
# ---------------------------------------------------------------------------


def define_network_site(
    *,
    site_did: str,
    name: str,
    kind: str = "edge-pop",
    backhaul_did: str = "",
) -> CimRecord:
    """Register a network site (edge PoP / aggregation / core)."""
    app, record_kind = "open-network", "network-site"
    if not site_did:
        return _missing("SiteDid", app, record_kind)
    if not name:
        return _missing("Name", app, record_kind)
    return _stub(
        app=app,
        record_kind=record_kind,
        name=name,
        detail={
            "siteDid": site_did,
            "name": name,
            "kind": kind,
            "backhaulDid": backhaul_did,
        },
    )


def define_network_link(
    *,
    from_site_did: str,
    to_site_did: str,
    bandwidth_gbps: float,
    medium: str = "fiber",
) -> CimRecord:
    """Register a point-to-point link between two network sites."""
    app, record_kind = "open-network", "network-link"
    if not from_site_did:
        return _missing("FromSiteDid", app, record_kind)
    if not to_site_did:
        return _missing("ToSiteDid", app, record_kind)
    if bandwidth_gbps is None:
        return _missing("BandwidthGbps", app, record_kind)
    name = (
        f"link-{_slugify(from_site_did.split(':')[-1])}"
        f"-{_slugify(to_site_did.split(':')[-1])}"
    )
    return _stub(
        app=app,
        record_kind=record_kind,
        name=name,
        detail={
            "fromSiteDid": from_site_did,
            "toSiteDid": to_site_did,
            "bandwidthGbps": float(bandwidth_gbps),
            "medium": medium,
        },
    )


# ---------------------------------------------------------------------------
# open-ot — critical handoff target (CommissioningCell → WASM PLC)
# ---------------------------------------------------------------------------


def define_loop(
    *,
    site_did: str,
    name: str,
    cell_dids: list[str],
    cadence_hz: float,
    safety_class: str = "non-SIL",
    wasm_module_cid: str = "",
) -> CimRecord:
    """Hand off steady-state control from kuni-umi (transient) to an open-ot
    WASM PLC loop (persistent).

    `cell_dids` are open-ot cells per IEC 61499.

    Per ADR-2605201400 §3 P3, kuni-umi never drives hard-RT motion: when this
    adapter is called by kuni-umi, `cadence_hz` must be <= 10 Hz. The override
    env var `OPEN_UTILITY_ALLOW_HIGH_CADENCE=1` is reserved for non-kuni-umi
    callers (e.g. dedicated open-ot deployment scripts that own the SIL
    boundary).
    """
    app, kind = "open-ot", "loop"
    if not site_did:
        return _missing("SiteDid", app, kind)
    if not name:
        return _missing("Name", app, kind)
    if cadence_hz is None:
        return _missing("CadenceHz", app, kind)

    allow_high = os.environ.get(ALLOW_HIGH_CADENCE_ENV, "") == "1"
    if cadence_hz > KUNI_UMI_CADENCE_LIMIT_HZ and not allow_high:
        did = _mint_did(app, kind, name)
        rec = CimRecord(
            did=did,
            app=app,
            record_kind=kind,
            ok=False,
            stubbed=True,
            created_at=_utcnow_iso(),
            detail={
                "error": "CadenceExceedsKuniUmiBound",
                "limitHz": KUNI_UMI_CADENCE_LIMIT_HZ,
                "requestedHz": float(cadence_hz),
                "overrideEnv": ALLOW_HIGH_CADENCE_ENV,
            },
        )
        logger.warning(
            "open-utility stub: app=%s kind=%s REJECT cadence=%.3fHz (limit=%.1fHz) name=%s",
            app,
            kind,
            float(cadence_hz),
            KUNI_UMI_CADENCE_LIMIT_HZ,
            name,
        )
        return rec

    return _stub(
        app=app,
        record_kind=kind,
        name=name,
        detail={
            "siteDid": site_did,
            "name": name,
            "cellDids": list(cell_dids or []),
            "cadenceHz": float(cadence_hz),
            "safetyClass": safety_class,
            "wasmModuleCid": wasm_module_cid,
            "highCadenceOverride": allow_high,
        },
    )


# ---------------------------------------------------------------------------
# open-robo — Giemon fleet driver (used by ConstructionOrchestrationCell)
# ---------------------------------------------------------------------------


def dispatch_work_order(
    *,
    plan_did: str,
    cell_id: str,
    robot_did: str,
    operation: str,
    payload_cid: str = "",
) -> CimRecord:
    """Dispatch a work order to a single Giemon robot."""
    app, kind = "open-robo", "work-order"
    if not plan_did:
        return _missing("PlanDid", app, kind)
    if not cell_id:
        return _missing("CellId", app, kind)
    if not robot_did:
        return _missing("RobotDid", app, kind)
    if not operation:
        return _missing("Operation", app, kind)
    name = f"wo-{_slugify(cell_id)}-{_slugify(operation)}-{uuid.uuid4().hex[:6]}"
    return _stub(
        app=app,
        record_kind=kind,
        name=name,
        detail={
            "planDid": plan_did,
            "cellId": cell_id,
            "robotDid": robot_did,
            "operation": operation,
            "payloadCid": payload_cid,
        },
    )


def poll_fleet_status(*, fleet_did: str) -> dict[str, Any]:
    """Poll the Giemon fleet for current robot status.

    Returns a dict (NOT a CimRecord) so callers can iterate `robots[]`
    directly. In stub mode returns a synthetic 2-robot fleet.
    """
    if not fleet_did:
        return {
            "ok": False,
            "stubbed": True,
            "error": "MissingFleetDid",
            "createdAt": _utcnow_iso(),
        }
    now = _utcnow_iso()
    robots = [
        {
            "robotDid": f"{DID_PREFIX}:open-robo:robot:{_slugify(fleet_did.split(':')[-1])}-0",
            "status": "idle",
            "currentTaskDid": "",
            "batteryPct": 92.0,
        },
        {
            "robotDid": f"{DID_PREFIX}:open-robo:robot:{_slugify(fleet_did.split(':')[-1])}-1",
            "status": "working",
            "currentTaskDid": f"{DID_PREFIX}:open-robo:work-order:synthetic-{uuid.uuid4().hex[:6]}",
            "batteryPct": 68.5,
        },
    ]
    logger.info(
        "open-utility stub: app=open-robo kind=fleet-status fleet=%s robots=%d",
        fleet_did,
        len(robots),
    )
    return {
        "ok": True,
        "stubbed": True,
        "fleetDid": fleet_did,
        "robots": robots,
        "polledAt": now,
    }


# ---------------------------------------------------------------------------
# Module-level metadata
# ---------------------------------------------------------------------------


#: Adapter functions exposed by this module. Count must match `healthz()`.
CIM_RECORD_FUNCTIONS: tuple[str, ...] = (
    # open-denki (4)
    "define_generation_node",
    "define_substation",
    "define_feeder",
    "register_smart_meter",
    # open-gas (2)
    "define_regulator",
    "define_pipe_segment",
    # open-water (2)
    "define_reservoir",
    "define_main",
    # open-network (2)
    "define_network_site",
    "define_network_link",
    # open-ot (1)
    "define_loop",
    # open-robo (2)
    "dispatch_work_order",
    "poll_fleet_status",
    # module-level (1)
    "healthz",
)


def healthz() -> dict[str, Any]:
    """Lightweight liveness probe. Reports adapter mode + capability surface."""
    return {
        "ok": True,
        "module": "kotodama.adapters.open_utility",
        "adapterMode": ADAPTER_MODE,
        "supportedApps": list(SUPPORTED_APPS),
        "cimRecordFunctions": len(CIM_RECORD_FUNCTIONS),
        "kuniUmiCadenceLimitHz": KUNI_UMI_CADENCE_LIMIT_HZ,
        "didPrefix": DID_PREFIX,
    }


__all__ = [
    "ADAPTER_MODE",
    "DID_PREFIX",
    "KUNI_UMI_CADENCE_LIMIT_HZ",
    "ALLOW_HIGH_CADENCE_ENV",
    "SUPPORTED_APPS",
    "CIM_RECORD_FUNCTIONS",
    "CimRecord",
    # open-denki
    "define_generation_node",
    "define_substation",
    "define_feeder",
    "register_smart_meter",
    # open-gas
    "define_regulator",
    "define_pipe_segment",
    # open-water
    "define_reservoir",
    "define_main",
    # open-network
    "define_network_site",
    "define_network_link",
    # open-ot
    "define_loop",
    # open-robo
    "dispatch_work_order",
    "poll_fleet_status",
    # module
    "healthz",
]
