# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c14121902 — Pulp Ingest (segment 14).

Bespoke implementation for tracking and validating the ingestion of pulp
raw materials into processing systems.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "14121902"
UNISPSC_TITLE = "Pulp Ingest"
UNISPSC_SEGMENT = "14"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c14121902"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Pulp Ingest
    pulp_batch_id: str
    moisture_content: float
    fiber_type: str
    screening_passed: bool
    ingest_timestamp: str


def validate_pulp_batch(state: State) -> dict[str, Any]:
    """Validates the incoming pulp batch metadata."""
    inp = state.get("input") or {}
    batch_id = inp.get("batch_id", "B-UNKNOWN")
    moisture = float(inp.get("moisture", 15.0))

    return {
        "log": [f"{UNISPSC_CODE}:validate_pulp_batch:{batch_id}"],
        "pulp_batch_id": batch_id,
        "moisture_content": moisture,
        "fiber_type": inp.get("fiber", "Virgin Kraft"),
    }


def analyze_consistency(state: State) -> dict[str, Any]:
    """Analyzes the moisture consistency and determines if screening is required."""
    moisture = state.get("moisture_content", 0.0)
    fiber = state.get("fiber_type", "")

    # Simulation: High moisture or recycled fiber requires stricter screening
    needs_intensive_screening = moisture > 25.0 or "recycled" in fiber.lower()

    return {
        "log": [f"{UNISPSC_CODE}:analyze_consistency:intensive={needs_intensive_screening}"],
        "screening_passed": not needs_intensive_screening,
    }


def record_ingest_event(state: State) -> dict[str, Any]:
    """Finalizes the ingest process and records the result."""
    passed = state.get("screening_passed", False)
    batch_id = state.get("pulp_batch_id")

    status = "INGESTED" if passed else "HOLD_FOR_INSPECTION"

    return {
        "log": [f"{UNISPSC_CODE}:record_ingest_event:{status}"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "batch_id": batch_id,
            "status": status,
            "ok": passed,
        },
    }


_g = StateGraph(State)

_g.add_node("validate", validate_pulp_batch)
_g.add_node("analyze", analyze_consistency)
_g.add_node("record", record_ingest_event)

_g.add_edge(START, "validate")
_g.add_edge("validate", "analyze")
_g.add_edge("analyze", "record")
_g.add_edge("record", END)

graph = _g.compile()
