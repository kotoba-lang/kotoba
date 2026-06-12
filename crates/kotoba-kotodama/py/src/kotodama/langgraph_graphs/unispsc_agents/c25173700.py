# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c25173700 — Emission (segment 25).

Bespoke graph logic for vehicle emission monitoring and reduction control.
This agent simulates the analysis of exhaust gas composition and the
activation of aftertreatment systems to ensure environmental compliance.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "25173700"
UNISPSC_TITLE = "Emission"
UNISPSC_SEGMENT = "25"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c25173700"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]

    # Emission-specific telemetry fields
    exhaust_temp_k: float
    nox_level_ppm: float
    aftertreatment_active: bool
    compliance_passed: bool


def analyze_telemetry(state: State) -> dict[str, Any]:
    """Analyzes incoming sensor data for exhaust temperature and NOx levels."""
    inp = state.get("input") or {}
    # Simulate reading from sensors (default values if missing)
    temp = float(inp.get("temperature", 550.0))
    nox = float(inp.get("nox_ppm", 180.0))

    return {
        "log": [f"{UNISPSC_CODE}:analyze_telemetry -> Temp={temp}K, NOx={nox}ppm"],
        "exhaust_temp_k": temp,
        "nox_level_ppm": nox,
    }


def control_aftertreatment(state: State) -> dict[str, Any]:
    """Determines if the emission reduction system (SCR/DPF) should be engaged."""
    temp = state.get("exhaust_temp_k", 0.0)
    nox = state.get("nox_level_ppm", 0.0)

    # Systems typically require a minimum temperature to be effective
    active = temp > 480.0 and nox > 20.0

    # If active, simulate reduction in pollutants
    final_nox = nox * 0.15 if active else nox

    return {
        "log": [f"{UNISPSC_CODE}:control_aftertreatment -> active={active}, final_nox={final_nox:.1f}"],
        "aftertreatment_active": active,
        "nox_level_ppm": final_nox,
    }


def certify_emission(state: State) -> dict[str, Any]:
    """Finalizes the emission state and verifies regulatory compliance."""
    nox = state.get("nox_level_ppm", 0.0)
    passed = nox < 30.0

    return {
        "log": [f"{UNISPSC_CODE}:certify_emission -> passed={passed}"],
        "compliance_passed": passed,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "telemetry": {
                "nox_ppm": round(nox, 2),
                "compliant": passed,
                "aftertreatment": state.get("aftertreatment_active")
            },
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("analyze", analyze_telemetry)
_g.add_node("control", control_aftertreatment)
_g.add_node("certify", certify_emission)

_g.add_edge(START, "analyze")
_g.add_edge("analyze", "control")
_g.add_edge("control", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
