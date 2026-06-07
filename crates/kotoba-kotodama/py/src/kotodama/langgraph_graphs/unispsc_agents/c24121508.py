# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c24121508 — Egg Tray (segment 24).

Bespoke graph logic for managing egg tray specifications, safety compliance,
and batch evaluation.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "24121508"
UNISPSC_TITLE = "Egg Tray"
UNISPSC_SEGMENT = "24"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c24121508"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Egg Tray
    tray_material: str
    cell_count: int
    is_food_safe: bool
    structural_integrity: float


def validate_specs(state: State) -> dict[str, Any]:
    """Validate the physical dimensions and material of the egg tray."""
    inp = state.get("input") or {}
    material = inp.get("material", "molded pulp")
    count = inp.get("count", 12)
    return {
        "log": [f"{UNISPSC_CODE}:validate_specs(material={material}, count={count})"],
        "tray_material": material,
        "cell_count": count,
    }


def assess_safety(state: State) -> dict[str, Any]:
    """Assess if the tray meets food safety standards based on material."""
    material = state.get("tray_material", "unknown")
    # Logic: Only pulp and specific plastics are marked as food safe in this simulation
    food_safe = material.lower() in ["molded pulp", "pet", "recycled fiber", "pulp"]
    return {
        "log": [f"{UNISPSC_CODE}:assess_safety(food_safe={food_safe})"],
        "is_food_safe": food_safe,
    }


def evaluate_batch(state: State) -> dict[str, Any]:
    """Evaluate structural integrity and finalize the agent result."""
    # Simulation: cell count influences structural score
    count = state.get("cell_count", 0)
    score = 0.98 if count <= 30 else 0.88

    is_ok = state.get("is_food_safe", False) and score > 0.85

    return {
        "log": [f"{UNISPSC_CODE}:evaluate_batch(score={score}, ok={is_ok})"],
        "structural_integrity": score,
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "metadata": {
                "material": state.get("tray_material"),
                "cells": count,
                "safety_verified": state.get("is_food_safe"),
                "integrity_score": score,
            },
            "ok": is_ok,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_specs)
_g.add_node("assess", assess_safety)
_g.add_node("evaluate", evaluate_batch)

_g.add_edge(START, "validate")
_g.add_edge("validate", "assess")
_g.add_edge("assess", "evaluate")
_g.add_edge("evaluate", END)

graph = _g.compile()
