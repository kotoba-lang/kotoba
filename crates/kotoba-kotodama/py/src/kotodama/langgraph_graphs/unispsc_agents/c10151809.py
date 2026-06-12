# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10151809 — Seed.
Bespoke graph logic for validating seed lot quality, moisture levels,
and germination standards within the Etz Hayyim plant material network.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10151809"
UNISPSC_TITLE = "Seed"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10151809"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain fields for Seed management
    lot_number: str
    germination_rate: float
    moisture_content: float
    purity_pct: float
    is_certified: bool


def intake_and_verify(state: State) -> dict[str, Any]:
    """Validates the incoming seed shipment manifest and lot identifier."""
    inp = state.get("input") or {}
    lot = inp.get("lot_number", "L-DEFAULT")

    # Simulate extraction of lot-specific data
    return {
        "log": [f"{UNISPSC_CODE}:intake_and_verify:{lot}"],
        "lot_number": lot,
        "is_certified": inp.get("certified", False),
    }


def quality_assurance(state: State) -> dict[str, Any]:
    """Performs simulated germination and moisture tests on the seed sample."""
    # Logic: In a real system these would be fetched from a laboratory LIMS
    germ_rate = 0.92
    moisture = 11.5
    purity = 99.8

    return {
        "log": [f"{UNISPSC_CODE}:quality_assurance:germ={germ_rate}:moist={moisture}"],
        "germination_rate": germ_rate,
        "moisture_content": moisture,
        "purity_pct": purity,
    }


def certification_registry(state: State) -> dict[str, Any]:
    """Finalizes the state into a formal actor-signed result dictionary."""
    lot = state.get("lot_number")
    germ = state.get("germination_rate", 0.0)
    moist = state.get("moisture_content", 0.0)

    # Business rule: Seeds must have >85% germination and <13% moisture
    is_standard = germ >= 0.85 and moist <= 13.0

    res = {
        "code": UNISPSC_CODE,
        "title": UNISPSC_TITLE,
        "did": UNISPSC_DID,
        "lot_number": lot,
        "quality_metrics": {
            "germination": germ,
            "moisture": moist,
            "purity": state.get("purity_pct", 0.0)
        },
        "status": "QUALIFIED" if is_standard else "REJECTED",
        "ok": True,
    }

    return {
        "log": [f"{UNISPSC_CODE}:certification_registry:{res['status']}"],
        "result": res,
    }


_g = StateGraph(State)
_g.add_node("intake_and_verify", intake_and_verify)
_g.add_node("quality_assurance", quality_assurance)
_g.add_node("certification_registry", certification_registry)

_g.add_edge(START, "intake_and_verify")
_g.add_edge("intake_and_verify", "quality_assurance")
_g.add_edge("quality_assurance", "certification_registry")
_g.add_edge("certification_registry", END)

graph = _g.compile()
