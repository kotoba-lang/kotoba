# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c21101902 — Pest Control Traps (segment 21).

Bespoke graph for managing agricultural pest trap telemetry, monitoring
capture levels, and assessing lure effectiveness in field environments.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "21101902"
UNISPSC_TITLE = ""
UNISPSC_SEGMENT = "21"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c21101902"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific state for agricultural traps
    target_species: str
    lure_potency_pct: float
    capture_count: int
    threshold_exceeded: bool


def calibrate_sensor(state: State) -> dict[str, Any]:
    """Calibrates the trap sensors and identifies the target pest species."""
    inp = state.get("input") or {}
    pest = inp.get("target_pest", "General Agricultural Pest")
    potency = float(inp.get("lure_potency", 100.0))

    return {
        "log": [f"{UNISPSC_CODE}:calibrate_sensor"],
        "target_species": pest,
        "lure_potency_pct": potency,
    }


def tally_captures(state: State) -> dict[str, Any]:
    """Tallies pest captures and determines if infestation thresholds are met."""
    inp = state.get("input") or {}
    raw_hits = int(inp.get("sensor_hits", 0))
    limit = int(inp.get("infestation_limit", 25))

    # Adjust hits by lure potency (simulated detection efficiency)
    effective_tally = int(raw_hits * (state.get("lure_potency_pct", 100.0) / 100.0))

    return {
        "log": [f"{UNISPSC_CODE}:tally_captures"],
        "capture_count": effective_tally,
        "threshold_exceeded": effective_tally >= limit,
    }


def generate_status(state: State) -> dict[str, Any]:
    """Generates pest management recommendations and final status report."""
    is_alert = state.get("threshold_exceeded", False)
    status_code = "INTERVENTION_REQUIRED" if is_alert else "NOMINAL"

    return {
        "log": [f"{UNISPSC_CODE}:generate_status"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "pest_profile": state.get("target_species"),
            "count": state.get("capture_count"),
            "status": status_code,
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("calibrate_sensor", calibrate_sensor)
_g.add_node("tally_captures", tally_captures)
_g.add_node("generate_status", generate_status)

_g.add_edge(START, "calibrate_sensor")
_g.add_edge("calibrate_sensor", "tally_captures")
_g.add_edge("tally_captures", "generate_status")
_g.add_edge("generate_status", END)

graph = _g.compile()
