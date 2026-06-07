# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c12352201 — Adhesion.

Bespoke graph logic for chemical adhesion properties and bonding processes.
This agent analyzes substrate compatibility, calculates curing parameters,
and verifies the structural integrity of the resulting bond.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "12352201"
UNISPSC_TITLE = "Adhesion"
UNISPSC_SEGMENT = "12"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c12352201"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], add]
    result: dict[str, Any]
    substrate_material: str
    bonding_strength_psi: int
    curing_temperature_c: float
    is_verified: bool


def analyze_substrate(state: State) -> dict[str, Any]:
    """Evaluates the surface material to determine optimal adhesive application."""
    inp = state.get("input") or {}
    material = inp.get("material", "unknown")

    # Determine curing temperature based on material sensitivity
    temp = 25.0  # Default room temp
    if material == "thermoplastic":
        temp = 45.5
    elif material == "metal":
        temp = 80.0

    return {
        "log": [f"{UNISPSC_CODE}:analyze_substrate"],
        "substrate_material": material,
        "curing_temperature_c": temp,
    }


def calculate_bond_strength(state: State) -> dict[str, Any]:
    """Simulates the chemical bonding process and predicts PSI strength."""
    material = state.get("substrate_material", "unknown")

    # Base strength calculation logic
    strength_map = {
        "metal": 2500,
        "thermoplastic": 1200,
        "wood": 800,
        "unknown": 100
    }
    predicted_psi = strength_map.get(material, 100)

    return {
        "log": [f"{UNISPSC_CODE}:calculate_bond_strength"],
        "bonding_strength_psi": predicted_psi,
    }


def verify_adhesion_integrity(state: State) -> dict[str, Any]:
    """Final quality assurance check for the adhesion process."""
    strength = state.get("bonding_strength_psi", 0)
    temp = state.get("curing_temperature_c", 0.0)

    # Validation threshold: 500 PSI minimum for industrial compliance
    is_ok = strength >= 500

    return {
        "log": [f"{UNISPSC_CODE}:verify_adhesion_integrity"],
        "is_verified": is_ok,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "metrics": {
                "strength_psi": strength,
                "curing_temp": temp,
                "material": state.get("substrate_material")
            },
            "ok": is_ok,
        },
    }


_g = StateGraph(State)

_g.add_node("analyze_substrate", analyze_substrate)
_g.add_node("calculate_bond_strength", calculate_bond_strength)
_g.add_node("verify_adhesion_integrity", verify_adhesion_integrity)

_g.add_edge(START, "analyze_substrate")
_g.add_edge("analyze_substrate", "calculate_bond_strength")
_g.add_edge("calculate_bond_strength", "verify_adhesion_integrity")
_g.add_edge("verify_adhesion_integrity", END)

graph = _g.compile()
