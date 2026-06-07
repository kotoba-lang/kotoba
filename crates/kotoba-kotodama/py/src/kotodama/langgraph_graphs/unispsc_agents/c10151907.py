# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10151907 — Mining Bit (segment 10).

Bespoke graph logic for evaluating mining bit durability and performance
metrics based on geological conditions and operational depth.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10151907"
UNISPSC_TITLE = "Mining Bit"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10151907"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    bit_type: str
    rock_hardness: float
    abrasion_factor: float
    calculated_wear: float


def analyze_geology(state: State) -> dict[str, Any]:
    """Inspects geological input to set baseline bit stress factors."""
    inp = state.get("input") or {}
    hardness = float(inp.get("hardness", 7.5))
    abrasion = float(inp.get("abrasion", 1.2))
    return {
        "log": [f"{UNISPSC_CODE}:analyze_geology (hardness={hardness})"],
        "rock_hardness": hardness,
        "abrasion_factor": abrasion,
    }


def calculate_bit_wear(state: State) -> dict[str, Any]:
    """Calculates cumulative bit wear based on depth and rock properties."""
    inp = state.get("input") or {}
    bit_type = inp.get("bit_type", "PDC")
    depth = float(inp.get("depth", 500.0))

    hardness = state.get("rock_hardness", 1.0)
    abrasion = state.get("abrasion_factor", 1.0)

    # Heuristic wear calculation: (depth * hardness * abrasion)
    wear = (depth * hardness * abrasion) / 10000.0
    return {
        "log": [f"{UNISPSC_CODE}:calculate_bit_wear (type={bit_type}, wear={wear:.4f})"],
        "bit_type": bit_type,
        "calculated_wear": wear,
    }


def validate_bit_integrity(state: State) -> dict[str, Any]:
    """Determines if the bit requires immediate replacement or maintenance."""
    wear = state.get("calculated_wear", 0.0)
    critical = wear > 0.85
    return {
        "log": [f"{UNISPSC_CODE}:validate_bit_integrity (critical={critical})"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "wear_score": round(wear, 4),
            "replacement_recommended": critical,
            "bit_type": state.get("bit_type"),
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("analyze_geology", analyze_geology)
_g.add_node("calculate_bit_wear", calculate_bit_wear)
_g.add_node("validate_bit_integrity", validate_bit_integrity)

_g.add_edge(START, "analyze_geology")
_g.add_edge("analyze_geology", "calculate_bit_wear")
_g.add_edge("calculate_bit_wear", "validate_bit_integrity")
_g.add_edge("validate_bit_integrity", END)

graph = _g.compile()
