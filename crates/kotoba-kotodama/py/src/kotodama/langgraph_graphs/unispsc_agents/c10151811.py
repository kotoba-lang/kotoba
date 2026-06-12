# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10151811 — Commodity.
Handles lifecycle and valuation for live animal commodities under segment 10.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10151811"
UNISPSC_TITLE = "Commodity"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10151811"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain specific fields for segment 10 Commodities
    commodity_class: str
    unit_count: int
    inspection_grade: str
    market_valuation: float


def triage_commodity(state: State) -> dict[str, Any]:
    """Categorizes the commodity and validates initial lot data."""
    inp = state.get("input") or {}
    comm_class = inp.get("class", "general_livestock")
    units = int(inp.get("units", 1))

    return {
        "log": [f"{UNISPSC_CODE}:triage_commodity"],
        "commodity_class": comm_class,
        "unit_count": units
    }


def appraise_market_value(state: State) -> dict[str, Any]:
    """Calculates the estimated market value based on commodity class and count."""
    units = state.get("unit_count", 0)
    comm_class = state.get("commodity_class", "general_livestock")

    # Mock grades and rates
    grade = "Grade-A" if units > 10 else "Standard"
    base_rate = 250.0 if comm_class == "premium" else 125.0
    valuation = float(units * base_rate)

    return {
        "log": [f"{UNISPSC_CODE}:appraise_market_value"],
        "inspection_grade": grade,
        "market_valuation": valuation
    }


def generate_commodity_report(state: State) -> dict[str, Any]:
    """Constructs the final actor output with valuation and classification data."""
    return {
        "log": [f"{UNISPSC_CODE}:generate_commodity_report"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "segment": UNISPSC_SEGMENT,
            "did": UNISPSC_DID,
            "class": state.get("commodity_class"),
            "valuation": state.get("market_valuation"),
            "grade": state.get("inspection_grade"),
            "verified": True,
            "ok": True
        }
    }


_g = StateGraph(State)
_g.add_node("triage", triage_commodity)
_g.add_node("appraise", appraise_market_value)
_g.add_node("report", generate_commodity_report)

_g.add_edge(START, "triage")
_g.add_edge("triage", "appraise")
_g.add_edge("appraise", "report")
_g.add_edge("report", END)

graph = _g.compile()
