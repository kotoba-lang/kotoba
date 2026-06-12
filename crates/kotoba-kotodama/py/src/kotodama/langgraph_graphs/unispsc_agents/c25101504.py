# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25101504 — Vehicle.

Bespoke graph logic for vehicle state management, including VIN validation,
system diagnostics, and dispatch readiness checks.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25101504"
UNISPSC_TITLE = "Vehicle"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25101504"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    vin_verified: bool
    maintenance_score: float
    telemetry_status: str
    dispatch_ready: bool


def inspect_vehicle(state: State) -> dict[str, Any]:
    """Validates the identity and registration of the vehicle asset."""
    inp = state.get("input") or {}
    vin = str(inp.get("vin", ""))
    # Mock VIN verification logic (checking standard length)
    is_valid = len(vin) == 17
    return {
        "log": [f"{UNISPSC_CODE}:inspect_vehicle:vin_check={is_valid}"],
        "vin_verified": is_valid,
    }


def diagnose_systems(state: State) -> dict[str, Any]:
    """Evaluates telemetry data to determine mechanical health."""
    inp = state.get("input") or {}
    telemetry = inp.get("telemetry") or {}

    # Simple diagnostic heuristic
    faults = telemetry.get("fault_codes", [])
    score = 1.0 - (len(faults) * 0.2)
    status = "nominal" if score >= 0.8 else "maintenance_required"

    return {
        "log": [f"{UNISPSC_CODE}:diagnose_systems:status={status}"],
        "maintenance_score": max(0.0, score),
        "telemetry_status": status,
    }


def finalize_manifest(state: State) -> dict[str, Any]:
    """Compiles the final status and determines if the vehicle is ready for operation."""
    is_verified = state.get("vin_verified", False)
    score = state.get("maintenance_score", 0.0)
    ready = is_verified and score > 0.7

    return {
        "log": [f"{UNISPSC_CODE}:finalize_manifest:ready={ready}"],
        "dispatch_ready": ready,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metrics": {
                "vin_verified": is_verified,
                "health_score": score,
                "operational_status": state.get("telemetry_status"),
            },
            "ok": ready,
        },
    }


_g = StateGraph(State)

_g.add_node("inspect", inspect_vehicle)
_g.add_node("diagnose", diagnose_systems)
_g.add_node("finalize", finalize_manifest)

_g.add_edge(START, "inspect")
_g.add_edge("inspect", "diagnose")
_g.add_edge("diagnose", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
