# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c11101615 — Metal Procure (segment 11).

Bespoke LangGraph implementation for metal procurement workflows, including
specification validation, sourcing simulation, and procurement finalization.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "11101615"
UNISPSC_TITLE = "Metal Procure"
UNISPSC_SEGMENT = "11"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c11101615"


class State(TypedDict, total=False):
    # Core fields
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]

    # Domain specific fields for Metal Procure
    metal_type: str
    purity_requirement: float
    quantity_metric_tons: float
    specification_validated: bool
    sourcing_strategy: str


def validate_specs(state: State) -> dict[str, Any]:
    """Validates the incoming procurement request against metallurgy standards."""
    inp = state.get("input") or {}
    metal = inp.get("metal_type", "unspecified")
    purity = float(inp.get("purity", 0.99))
    quantity = float(inp.get("quantity", 0.0))

    valid = purity >= 0.95 and quantity > 0

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs:{metal}:valid={valid}"],
        "metal_type": metal,
        "purity_requirement": purity,
        "quantity_metric_tons": quantity,
        "specification_validated": valid,
    }


def source_metal(state: State) -> dict[str, Any]:
    """Simulates selecting a sourcing strategy based on quantity and purity."""
    if not state.get("specification_validated"):
        return {"log": [f"{UNISPSC_CODE}:source_metal:skipped"], "sourcing_strategy": "rejected"}

    qty = state.get("quantity_metric_tons", 0)
    strategy = "spot_market" if qty < 100 else "direct_contract"

    return {
        "log": [f"{UNISPSC_CODE}:source_metal:strategy={strategy}"],
        "sourcing_strategy": strategy,
    }


def finalize_procurement(state: State) -> dict[str, Any]:
    """Finalizes the procurement record and prepares the output result."""
    valid = state.get("specification_validated", False)
    strategy = state.get("sourcing_strategy", "none")

    return {
        "log": [f"{UNISPSC_CODE}:finalize_procurement"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "status": "completed" if valid else "failed",
            "details": {
                "strategy": strategy,
                "purity_checked": state.get("purity_requirement"),
                "volume": state.get("quantity_metric_tons")
            }
        },
    }


_g = StateGraph(State)

_g.add_node("validate_specs", validate_specs)
_g.add_node("source_metal", source_metal)
_g.add_node("finalize_procurement", finalize_procurement)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "source_metal")
_g.add_edge("source_metal", "finalize_procurement")
_g.add_edge("finalize_procurement", END)

graph = _g.compile()
