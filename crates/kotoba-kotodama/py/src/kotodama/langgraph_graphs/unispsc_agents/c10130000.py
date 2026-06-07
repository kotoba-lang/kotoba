# codemod:2605231400-unispsc-gemini-bespoke v1
"""
Unispsc actor agent c10130000 — Seed (segment 10).

Bespoke logic for seed lot validation, quality testing, and certification.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

UNISPSC_CODE = "10130000"
UNISPSC_TITLE = "Seed"
UNISPSC_SEGMENT = "10"
UNISPSC_DID = "did:web:etzhayyim.com:actor:c10130000"


class State(TypedDict, total=False):
    input: dict[str, Any]
    log: Annotated[list[str], operator.add]
    result: dict[str, Any]
    # Domain state for Seed
    seed_variety: str
    germination_rate: float
    moisture_content: float
    purity_level: float
    lot_id: str


def validate_seed_lot(state: State) -> dict[str, Any]:
    """Initial check of the seed lot metadata and variety registration."""
    inp = state.get("input") or {}
    variety = inp.get("variety", "Standard-Grade-Seed")
    lot_id = inp.get("lot_id", "LOT-SEED-PENDING")
    return {
        "log": [f"{UNISPSC_CODE}:validate_seed_lot"],
        "seed_variety": variety,
        "lot_id": lot_id,
    }


def perform_quality_test(state: State) -> dict[str, Any]:
    """Simulates laboratory testing for germination, moisture, and purity."""
    # In a real scenario, this might pull from a lab results database
    variety = state.get("seed_variety", "")
    is_premium = "Premium" in variety

    return {
        "log": [f"{UNISPSC_CODE}:perform_quality_test"],
        "germination_rate": 0.98 if is_premium else 0.88,
        "moisture_content": 12.2,
        "purity_level": 99.9,
    }


def issue_certification(state: State) -> dict[str, Any]:
    """Certifies the seed lot based on quality metrics and issues result."""
    germ = state.get("germination_rate", 0)
    purity = state.get("purity_level", 0)
    # Certification threshold: 90% germination and 99% purity
    certified = germ >= 0.90 and purity >= 99.0

    return {
        "log": [f"{UNISPSC_CODE}:issue_certification"],
        "result": {
            "code": UNISPSC_CODE,
            "title": UNISPSC_TITLE,
            "did": UNISPSC_DID,
            "lot_id": state.get("lot_id"),
            "variety": state.get("seed_variety"),
            "status": "CERTIFIED" if certified else "REJECTED",
            "metrics": {
                "germination": germ,
                "purity": purity,
                "moisture": state.get("moisture_content")
            },
            "ok": True,
        },
    }


_g = StateGraph(State)
_g.add_node("validate", validate_seed_lot)
_g.add_node("test", perform_quality_test)
_g.add_node("certify", issue_certification)

_g.add_edge(START, "validate")
_g.add_edge("validate", "test")
_g.add_edge("test", "certify")
_g.add_edge("certify", END)

graph = _g.compile()
