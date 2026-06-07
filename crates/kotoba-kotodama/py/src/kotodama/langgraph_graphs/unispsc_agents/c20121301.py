# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121301"
UNISPSC_TITLE = "Robot Motor"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121301"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    # Domain fields for Robot Motor
    voltage_v: float
    rated_torque_nm: float
    encoder_integrated: bool
    thermal_protection_active: bool
    certification_status: str


def validate_specs(state: State) -> dict[str, Any]:
    """Validate mechanical and electrical specifications for the robot motor."""
    inp = state.get("input") or {}
    voltage = float(inp.get("voltage", 24.0))
    torque = float(inp.get("torque", 0.5))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "voltage_v": voltage,
        "rated_torque_nm": torque,
        "certification_status": "pending_audit" if voltage > 0 else "invalid_power",
    }


def perform_safety_audit(state: State) -> dict[str, Any]:
    """Audit safety systems including thermal protection and feedback encoders."""
    inp = state.get("input") or {}
    has_encoder = bool(inp.get("encoder", True))
    has_thermal = bool(inp.get("thermal_cutout", True))

    current_status = state.get("certification_status", "unknown")
    if has_thermal and current_status == "pending_audit":
        new_status = "safety_verified"
    else:
        new_status = current_status

    return {
        "log": [f"{UNISPSC_CODE}:perform_safety_audit"],
        "encoder_integrated": has_encoder,
        "thermal_protection_active": has_thermal,
        "certification_status": new_status,
    }


def generate_asset_record(state: State) -> dict[str, Any]:
    """Generate the final asset metadata for the Robot Motor."""
    status = state.get("certification_status", "failed")

    return {
        "log": [f"{UNISPSC_CODE}:generate_asset_record"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "voltage": state.get("voltage_v"),
                "torque": state.get("rated_torque_nm"),
                "encoder": state.get("encoder_integrated"),
                "thermal": state.get("thermal_protection_active"),
                "status": status,
            },
            "ok": status == "safety_verified",
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specs)
_g.add_node("audit", perform_safety_audit)
_g.add_node("emit", generate_asset_record)

_g.add_edge(START, "validate")
_g.add_edge("validate", "audit")
_g.add_edge("audit", "emit")
_g.add_edge("emit", END)

graph = _g.compile()
