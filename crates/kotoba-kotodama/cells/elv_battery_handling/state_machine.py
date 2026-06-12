"""ELV battery handling state machine — ADR-2605261215 L2 (hodoki).

Li-ion SoH classification (≥70% → hikari R2+ stationary second-life;
<70% → cell-recycle Wave 2 ADR); lead-acid → kanayama Wave 3.
G7 thermal-safety SOP: no puncture, no short-circuit, thermal-runaway
containment enclosure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class BatteryPhase(Enum):
    INIT = "init"
    THERMAL_BASELINE = "thermal_baseline"
    SOH_MEASURED = "soh_measured"
    ROUTING_DECIDED = "routing_decided"
    ATTESTATION_EMITTED = "attestation_emitted"


@dataclass
class BatteryState:
    phase: BatteryPhase
    vehicleId: str
    completionPct: int
    thermalBaseline: dict[str, Any] | None = None
    sohMeasurement: dict[str, Any] | None = None
    routing: dict[str, Any] | None = None
    robotSignatures: list[dict[str, Any]] = field(default_factory=list)


def transition_to_thermal_baseline(state: dict[str, Any]) -> dict[str, Any]:
    """INIT → THERMAL_BASELINE. G7 thermal-safety pre-handling check."""
    bh = BatteryState(**state.get("battery_state", {}))
    mock_thermal = {
        "ambientTempC": 22,
        "cellTempCMax": 24,
        "cellTempCMin": 22,
        "deltaCellTempC": 2,
        "thermalRunawayContainmentEnclosure": True,
        "punctureRiskAssessed": "low",
        "shortCircuitRiskAssessed": "low",
        "g7CompliantBaseline": True,
    }
    bh.phase = BatteryPhase.THERMAL_BASELINE
    bh.thermalBaseline = mock_thermal
    bh.completionPct = 25
    return {"battery_state": bh.__dict__, "next_node": "soh"}


def transition_to_soh_measured(state: dict[str, Any]) -> dict[str, Any]:
    """THERMAL_BASELINE → SOH_MEASURED. Capacity test + impedance + cycle count."""
    bh = BatteryState(**state.get("battery_state", {}))
    mock_soh = {
        "chemistry": "Li-ion-NMC-622",
        "nominalKwh": 12.0,
        "measuredKwh": 9.4,
        "sohPct": 78.3,
        "cycleCount": 1240,
        "impedanceMohm": 35,
        "moduleHealthMap": "all-modules-within-5pct-of-mean",
        "measurementMethod": "ASTM-D6385-cycle-test-with-impedance",
        "ipfsTestCid": "bafkreisoh001...",
    }
    bh.phase = BatteryPhase.SOH_MEASURED
    bh.sohMeasurement = mock_soh
    bh.completionPct = 65
    return {"battery_state": bh.__dict__, "next_node": "routing"}


def transition_to_routing_decided(state: dict[str, Any]) -> dict[str, Any]:
    """SOH_MEASURED → ROUTING_DECIDED. ≥70% → hikari second-life; <70% → Wave 2 cell-recycle."""
    bh = BatteryState(**state.get("battery_state", {}))
    soh_pct = bh.sohMeasurement.get("sohPct", 0.0) if bh.sohMeasurement else 0.0
    mock_routing = {
        "sohPct": soh_pct,
        "thresholdPct": 70.0,
        "routingDecision": "second-life-hikari" if soh_pct >= 70.0 else "cell-recycle-wave2",
        "destinationActor": "hikari" if soh_pct >= 70.0 else "wave2-pending",
        "destinationDid": "did:web:etzhayyim.com:hikari:storage-r2",
        "g13CircularFeedConfirmed": True,
    }
    bh.phase = BatteryPhase.ROUTING_DECIDED
    bh.routing = mock_routing
    bh.completionPct = 90
    return {"battery_state": bh.__dict__, "next_node": "attestation"}


def transition_to_attestation_emitted(state: dict[str, Any]) -> dict[str, Any]:
    bh = BatteryState(**state.get("battery_state", {}))
    mock_sigs = [
        {
            "robotDid": "did:web:etzhayyim.com:otete-levi-unit-1",
            "role": "battery_handler",
            "timestamp": "2026-05-26T12:30:00Z",
            "signature": "qQ1rR2sS3tT4...",
        },
        {
            "robotDid": "did:web:etzhayyim.com:mimi-levi-unit-1",
            "role": "soh_metrology",
            "timestamp": "2026-05-26T12:30:05Z",
            "signature": "uU5vV6wW7xX8...",
        },
    ]
    bh.phase = BatteryPhase.ATTESTATION_EMITTED
    bh.robotSignatures = mock_sigs
    bh.completionPct = 100
    record = {
        "$type": "com.etzhayyim.hodoki.batteryHandlingRecord",
        "vehicleId": bh.vehicleId,
        "thermalBaseline": bh.thermalBaseline,
        "soh": bh.sohMeasurement,
        "routing": bh.routing,
        "g7Compliant": True,
        "attestingRobots": mock_sigs,
        "recordedAt": "2026-05-26T12:30:10Z",
    }
    return {"battery_state": bh.__dict__, "battery_handling_record": record, "next_node": "end"}
