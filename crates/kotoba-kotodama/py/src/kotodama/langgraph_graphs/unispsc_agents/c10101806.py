# codemod:2605231400-unispsc-gemini-bespoke v1
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10101806"
UNISPSC_TITLE = "Mining"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10101806"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain-specific fields for Mining
    site_id: str
    resource_category: str
    extraction_strategy: str
    environmental_clearance: bool
    projected_recovery_rate: float


def geological_survey(state: State) -> dict[str, Any]:
    """Analyzes geological data to identify mineral deposits and site viability."""
    inp = state.get("input") or {}
    site = inp.get("site_id", "LOC-MIN-101")
    resource = inp.get("resource", "Metallic Ores")

    return {
        "log": [f"{UNISPSC_CODE}:geological_survey"],
        "site_id": site,
        "resource_category": resource,
        "environmental_clearance": True,
    }


def resource_extraction_plan(state: State) -> dict[str, Any]:
    """Formulates the extraction methodology based on site profile."""
    resource = state.get("resource_category", "General")
    # Selection logic for mining methods
    if resource == "Metallic Ores":
        method = "Sub-level Stoping"
    elif resource == "Aggregates":
        method = "Open-pit Quarrying"
    else:
        method = "Drill and Blast"

    recovery = 0.88 if state.get("environmental_clearance") else 0.0

    return {
        "log": [f"{UNISPSC_CODE}:resource_extraction_plan"],
        "extraction_strategy": method,
        "projected_recovery_rate": recovery,
    }


def operational_summary(state: State) -> dict[str, Any]:
    """Consolidates mining parameters into a final operational status report."""
    is_active = state.get("environmental_clearance", False)

    return {
        "log": [f"{UNISPSC_CODE}:operational_summary"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "site": state.get("site_id"),
            "strategy": state.get("extraction_strategy"),
            "recovery_metric": f"{state.get('projected_recovery_rate', 0.0) * 100:.1f}%",
            "status": "APPROVED" if is_active else "PENDING_ENVIRONMENTAL_REVIEW",
        },
    }


_g = StateGraph(State)

_g.add_node("survey", geological_survey)
_g.add_node("plan", resource_extraction_plan)
_g.add_node("summarize", operational_summary)

_g.add_edge(START, "survey")
_g.add_edge("survey", "plan")
_g.add_edge("plan", "summarize")
_g.add_edge("summarize", END)

graph = _g.compile()
