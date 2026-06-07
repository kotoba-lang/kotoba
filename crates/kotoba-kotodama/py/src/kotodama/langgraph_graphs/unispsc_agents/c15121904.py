# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c15121904 — Lubricant (segment 15).

Bespoke graph logic for industrial lubricant specification, additive blending,
and quality certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "15121904"
UNISPSC_TITLE = "Lubricant"
UNISPSC_SEGMENT = "15"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c15121904"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for Lubricant
    viscosity_index: int
    base_oil_type: str
    additive_package: list[str]
    flash_point_celsius: int
    friction_coefficient: float


def validate_specs(state: State) -> dict[str, Any]:
    """Validates incoming lubricant requirements and determines base stock."""
    inp = state.get("input") or {}
    target_vg = inp.get("iso_vg", 46)

    # Determine base oil category based on target viscosity
    base_type = "Group III Synthetic" if target_vg > 68 else "Group II Mineral"

    return {
        "log": [f"{UNISPSC_CODE}:validate_specs"],
        "viscosity_index": target_vg,
        "base_oil_type": base_type,
        "flash_point_celsius": 210 if base_type.startswith("Group III") else 195,
    }


def formulate_blend(state: State) -> dict[str, Any]:
    """Simulates the addition of performance additives."""
    return {
        "log": [f"{UNISPSC_CODE}:formulate_blend"],
        "additive_package": ["Anti-wear", "Oxidation Inhibitor", "Corrosion Preventative"],
        "friction_coefficient": 0.08,
    }


def certify_batch(state: State) -> dict[str, Any]:
    """Final quality control and result emission."""
    return {
        "log": [f"{UNISPSC_CODE}:certify_batch"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "specification": {
                "base_oil": state.get("base_oil_type"),
                "viscosity": state.get("viscosity_index"),
                "additives": state.get("additive_package"),
                "performance": {
                    "friction": state.get("friction_coefficient"),
                    "flash_point": state.get("flash_point_celsius"),
                }
            },
            "compliance": True,
            "ok": True,
        },
    }


_g = StateGraph(State)

_g.add_node("validate_specs", validate_specs)
_g.add_node("formulate_blend", formulate_blend)
_g.add_node("certify_batch", certify_batch)

_g.add_edge(START, "validate_specs")
_g.add_edge("validate_specs", "formulate_blend")
_g.add_edge("formulate_blend", "certify_batch")
_g.add_edge("certify_batch", END)

graph = _g.compile()
