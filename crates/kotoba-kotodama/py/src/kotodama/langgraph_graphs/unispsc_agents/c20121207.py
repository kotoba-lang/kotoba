# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c20121207 — Motor (segment 20).

Bespoke LangGraph agent providing logic for Motor specification validation,
performance estimation, and configuration output.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "20121207"
UNISPSC_TITLE = "Motor"
UNISPSC_SEGMENT = "20"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c20121207"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific state for Motor
    rpm_rating: int
    voltage_spec: str
    efficiency_class: str
    is_brushless: bool
    config_valid: bool


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the input motor parameters."""
    inp = state.get("input") or {}
    rpm = inp.get("rpm", 1800)
    voltage = str(inp.get("voltage", "230V"))

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "rpm_rating": rpm,
        "voltage_spec": voltage,
        "config_valid": rpm > 0,
    }


def calculate_performance(state: State) -> dict[str, Any]:
    """Derives performance metrics based on motor specifications."""
    rpm = state.get("rpm_rating", 0)
    # Simple logic: higher RPM motors in this context are classified with better efficiency
    eff_class = "IE3" if rpm >= 1500 else "IE2"
    brushless = bool(state.get("input", {}).get("brushless", True))

    return {
        "log": [f"{UNISPSC_CODE}:calculate_performance"],
        "efficiency_class": eff_class,
        "is_brushless": brushless,
    }


def finalize_configuration(state: State) -> dict[str, Any]:
    """Constructs the final validated motor configuration response."""
    return {
        "log": [f"{UNISPSC_CODE}:finalize_configuration"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "specifications": {
                "rpm": state.get("rpm_rating"),
                "voltage": state.get("voltage_spec"),
                "efficiency": state.get("efficiency_class"),
                "brushless": state.get("is_brushless"),
            },
            "ok": state.get("config_valid", False),
        },
    }


_g = StateGraph(State)
_g.add_node("validate_specs", validate_specs)
_g.add_node("calculate_performance", calculate_performance)
_g.add_node("finalize_configuration", finalize_configuration)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "calculate_performance")
_g.add_edge("calculate_performance", "finalize_configuration")
_g.add_edge("finalize_configuration", END)

graph = _g.compile()
