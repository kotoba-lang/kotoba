# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121322 — Motor (segment 20).

Bespoke graph logic for handling motor specifications, performance validation,
and thermal compliance checking.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121322"
UNISPSC_TITLE = "Motor"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121322"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Extra fields for Motor domain
    specification_vetted: bool
    torque_nm: float
    rpm: int
    efficiency_percentage: float
    thermal_compliance: bool


def validate_motor_specs(state: State) -> dict[str, Any]:
    """Validate incoming motor parameters for basic operational range."""
    inp = state.get("input") or {}
    rpm = inp.get("rpm", 0)
    torque = inp.get("torque", 0.0)

    # Basic vetting: require positive values
    vetted = rpm > 0 and torque > 0
    return {
        "log": [f"{UNISPSC_CODE}:validate_motor_specs"],
        "specification_vetted": vetted,
        "rpm": rpm,
        "torque_nm": torque,
    }


def compute_efficiency(state: State) -> dict[str, Any]:
    """Calculate simulated efficiency and check thermal constraints based on RPM."""
    rpm = state.get("rpm", 0)
    torque = state.get("torque_nm", 0.0)

    # Simulated efficiency calculation: efficiency peaks at mid-range RPM
    base_eff = 0.92
    if rpm > 6000:
        base_eff -= 0.08
    elif rpm < 1000:
        base_eff -= 0.05

    # Thermal compliance check: high RPM generates excessive heat
    thermal_ok = rpm < 7500

    return {
        "log": [f"{UNISPSC_CODE}:compute_efficiency"],
        "efficiency_percentage": round(base_eff * 100, 2),
        "thermal_compliance": thermal_ok,
    }


def package_result(state: State) -> dict[str, Any]:
    """Emit the final validated motor performance profile."""
    vetted = state.get("specification_vetted", False)
    thermal = state.get("thermal_compliance", False)
    eff = state.get("efficiency_percentage", 0.0)

    success = vetted and thermal

    return {
        "log": [f"{UNISPSC_CODE}:package_result"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "metrics": {
                "efficiency": f"{eff}%",
                "thermal_compliance": thermal,
                "specification_vetted": vetted,
            },
            "status": "OPERATIONAL" if success else "OUT_OF_SPEC",
            "ok": success,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_motor_specs)
_g.add_node("compute", compute_efficiency)
_g.add_node("finalize", package_result)

_g.add_edge(START, "validate")
_g.add_edge("validate", "compute")
_g.add_edge("compute", "finalize")
_g.add_edge("finalize", END)

graph = _g.compile()
